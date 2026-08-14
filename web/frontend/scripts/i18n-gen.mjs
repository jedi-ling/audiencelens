#!/usr/bin/env node
/**
 * i18n codegen + 构建期卡口。owner: batch-0，页面 agent 只读。
 *
 *   node scripts/i18n-gen.mjs            改完资源后跑它，重新生成 *.gen.ts
 *   node scripts/i18n-gen.mjs --check    只校验，不写盘；任何一条不过就非零退出
 *
 * 为什么用 codegen 而不是递归 Paths<typeof zh> 类型推导（契约 7.1）：
 * 递归类型在 2000 个 key、深度 4 的对象上会顶到 TS 递归上限并显著拖慢 tsc -b，
 * 而 tsc -b 已经在 build 的关键路径上。更重要的是纯类型推导**只能保证 key 存在于
 * zh**，给不了这三条：zh/en 逻辑 key 集相等、插值变量名一致、en 复数变体完整
 * ——而这三条正是"缺译能被发现"的全部机制。类型推导只能防写错，防不了漏译。
 *
 * 生成物入库（committed），不每次构建现生成。这是刻意的：宁可多一次显式动作，
 * 也不要构建期现生成导致"本地过了 CI 没过"。
 *
 * 实现说明：直接 import 资源 .ts 文件（Node ≥22.6 的类型剥离），不做正则解析。
 * 正则解析 TS 会在第一个多行模板字符串或带转义引号的译文上悄悄漏掉条目，
 * 而漏掉的表现是"这条 key 不在 keys.gen.ts 里 → 页面 tsc 报错说 key 不存在"，
 * 排查方向完全错。让 Node 自己求值，形状不对就当场炸。
 */

import { readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { buildCatalogOutputs } from './i18n-sync-catalog.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
const I18N_DIR = join(ROOT, 'src', 'i18n')
const LOCALES_DIR = join(I18N_DIR, 'locales')
const MOCK_DATA = join(ROOT, 'src', 'lib', 'mock-data.ts')

/** 语料里存在的全部语言。与 VITE_AL_LOCALES（对用户开放的）是两回事。 */
const LOCALES = ['zh', 'en']
/** 事实源语言：MessageVars / MessageKey 以它为准，en 侧只做对齐校验。 */
const SOURCE = 'zh'

/** 域白名单（契约 3.1 第 1 段，闭集）。 */
const DOMAINS = new Set(['common', 'nav', 'page', 'enum', 'catalog', 'error'])

/**
 * 角色白名单（契约 3.2，闭集）。
 *
 * 只对**四段** key 的第 4 段生效；三段 key 的叶子（enum.severity.critical）不查。
 * 要加新角色：改这张表并跑 gen，由 batch-0 做，页面 agent 不得自造。
 * 不闭的话 12 个 agent 会写出 btn / button / action / cta 四种同义角色，
 * 半年后没人能靠 key 猜到文案在哪。
 */
const ROLES = new Set([
  'title', 'subtitle', 'desc', 'label', 'placeholder', 'hint', 'unit', 'value',
  'cta', 'link', 'tab', 'step', 'badge',
  'empty', 'loading', 'pending', 'success', 'error', 'confirm',
  'aria', 'tooltip', 'meta',
])

/**
 * 变体块：块内的叶子不受角色闭集约束。
 *
 * 这里替换了 batch-0 留下的逐条 ROLE_EXCEPTIONS 名单。契约 owner 的裁决：
 *
 * 闭集要防的是**同义角色漂移**——12 个 agent 写出 btn / button / action / cta
 * 四种说法，半年后没人能靠 key 猜到文案在哪。但 §3.4 那批例子
 * （page.history.count.total / .loaded_only / .total_and_loaded）根本不是这个
 * 问题：它们是同一句话的**互斥变体**，叶子名描述的是"哪个分支"，天然被第 3 段
 * 圈在一个块里，不会跨块串味。用角色词硬套反而会写出 count.value / count.value2
 * 这种更难懂的东西。
 *
 * 逐条豁免不可扩展：29 个文件跑完会攒出上百条，那张名单本身就成了没人看的垃圾场，
 * 而且每个 agent 都得回来找 owner 加一行——12 次同样的往返正是 batch-0 警告过的。
 *
 * 所以改成：**块名是闭集，块内叶子自由**。加一个新块 = 一次显式决定，diff 上看得见，
 * 而块内加分支不需要惊动任何人。
 */
const VARIANT_BLOCKS = new Set([
  'count', // 数量文案的多分支（有总数/只有已加载/两者都有）
  'load_more', // 分页按钮的多态
  'terms', // 条款同意句这类含内嵌链接的整句
  'state', // 一个控件的多个状态文案（发送中/已发送/失败/重试）
  'stage', // 流程阶段名
  'reason', // 失败/跳过原因的枚举式文案
])

/** 复数后缀。逻辑 key = 去掉它们之后的 key（契约 D9）。 */
const PLURAL_SUFFIXES = ['_zero', '_one', '_two', '_few', '_many', '_other']

/**
 * 允许 en 与 zh 字面完全相同的 key。
 * 目前全仓只有一条，理由写在 zh/common.action.ts 里：它是后端的字面量比较凭据，
 * 翻译它 = 英文用户永远删不掉账号。
 */
const SAME_TEXT_EXEMPT = new Set(['common.action.delete_account_phrase'])

const CJK = /[㐀-䶿一-鿿豈-﫿]/
const VAR_RE = /\{\{(\w+)\}\}/g
const SLOT_RE = /<(\w+)>([\s\S]*?)<\/\1>/g

const errors = []
const fail = (msg) => errors.push(msg)

/* ------------------------------------------------------------------ *
 * 1. 读资源
 * ------------------------------------------------------------------ */

function listResourceFiles(locale) {
  const dir = join(LOCALES_DIR, locale)
  if (!existsSync(dir)) {
    fail(`缺少语料目录 src/i18n/locales/${locale}/`)
    return []
  }
  return readdirSync(dir)
    .filter((f) => f.endsWith('.ts') && !f.endsWith('.gen.ts'))
    .sort()
}

async function loadLocale(locale) {
  /** @type {{ file: string, base: string, entries: [string, string][] }[]} */
  const files = []
  for (const file of listResourceFiles(locale)) {
    const base = file.slice(0, -3)
    const segs = base.split('.')
    if (segs.length !== 2) {
      fail(`[文件名] ${locale}/${file}：文件名必须恰好是 key 的前两段（<域>.<单元>.ts）`)
      continue
    }
    if (!DOMAINS.has(segs[0])) {
      fail(`[文件名] ${locale}/${file}：域 "${segs[0]}" 不在白名单 ${[...DOMAINS].join('|')}`)
      continue
    }
    let mod
    try {
      mod = await import(pathToFileURL(join(LOCALES_DIR, locale, file)).href)
    } catch (e) {
      fail(`[加载失败] ${locale}/${file}：${e.message}`)
      continue
    }
    const table = mod.default
    if (!table || typeof table !== 'object' || Array.isArray(table)) {
      fail(`[形状] ${locale}/${file}：default export 必须是扁平对象`)
      continue
    }
    const entries = []
    for (const [k, v] of Object.entries(table)) {
      if (typeof v !== 'string') {
        fail(`[形状] ${locale}/${file} 的 "${k}"：值必须是字符串，实得 ${typeof v}`)
        continue
      }
      entries.push([k, v])
    }
    files.push({ file, base, entries })
  }
  return files
}

const varsOf = (s) => new Set([...s.matchAll(VAR_RE)].map((m) => m[1]))
const slotsOf = (s) => new Set([...s.matchAll(SLOT_RE)].map((m) => m[1]))
const logicalKey = (k) => {
  const hit = PLURAL_SUFFIXES.find((suf) => k.endsWith(suf))
  return hit ? k.slice(0, -hit.length) : k
}

/* ------------------------------------------------------------------ *
 * 2. 绝对不能翻译的 wire 字符串（契约 12.2）
 *
 * 从 mock-data.ts 里现取，不写死副本——写死副本会在源改了之后静默失效，
 * 而失效的表现是"卡口还在跑、还是绿的、但已经不查任何东西了"。
 * ------------------------------------------------------------------ */

function wireStrings() {
  if (!existsSync(MOCK_DATA)) {
    fail(`[黑名单] 找不到 ${MOCK_DATA}，wire key 断言无法执行`)
    return new Set()
  }
  const src = readFileSync(MOCK_DATA, 'utf8')
  const out = new Set()

  // TASK_MATERIALS[].key —— 中文是 wire contract：CreateReviewPage 把它当
  // materials[].type 发给后端，后端 MaterialExtractor.TASK_FIELDS 按同样的
  // 中文字面量匹配。改了它 → 编译通过、界面正常、评审照跑 200，只是提取不到材料。
  const mat = src.match(/export const TASK_MATERIALS[\s\S]*?\n\}/)
  if (mat) for (const m of mat[0].matchAll(/\bkey:\s*'([^']+)'/g)) out.add(m[1])

  // stance_enum —— 后端 parity 测试逐字保护，且是引擎的聚类键。
  for (const m of src.matchAll(/stance_enum:\s*\[([^\]]*)\]/g)) {
    for (const s of m[1].matchAll(/'([^']+)'/g)) out.add(s[1])
  }

  if (out.size === 0) {
    fail('[黑名单] 从 mock-data.ts 里一个 wire 字符串都没抽到——正则失效了，别当成"没有问题"')
  }
  return out
}

/* ------------------------------------------------------------------ *
 * 2b. wire 黑名单对 zh 材料 overlay 的**定点豁免**
 *
 * 为什么需要它：TASK_MATERIALS 里有 16 个字段的 label 与它自己的 key 逐字相同
 * （`{ key: '目标受众', label: '目标受众', … }`）。这两个字符串长得一样，
 * 但身份完全不同：key 是发给后端的 wire，label 是画在输入框上的字。
 * 上面那条黑名单只认字符串、不认身份，于是把中文界面**本来就该显示的那行字**
 * 判成了"翻译 wire key"。
 *
 * 为什么豁免不会开洞：豁免的不是"这 16 个字符串随便用"，而是
 * "zh 侧这一条 key 的值必须**逐字等于 mock-data 里同一个字段的 label/placeholder**"。
 * 值对不上就照样红。所以想借这个口子把 wire key 塞进别的 key、或者把 zh 的显示文案
 * 改成另一个 wire 字符串，都过不去。
 * en 侧不豁免——英文界面显示中文 wire key 一定是错的。
 *
 * 为什么现取而不写死 16 条清单：写死的清单在 mock-data 改了之后会静默失效，
 * 且失效方向是"豁免仍然生效、但已经不对应任何真实字段"。现取则是源改了、
 * 豁免跟着改，对不上就红。
 *
 * 注意 wire 本身并没有因此变得可翻译：getMaterialFields 返回的 `key` 取自
 * TASK_MATERIALS 源常量（catalog.ts:89 `key: f.key`），从来不经过 key 表。
 * ------------------------------------------------------------------ */

function materialDisplayStrings() {
  const out = new Map()
  if (!existsSync(MOCK_DATA)) return out // 上面 wireStrings 已经报过找不到文件了
  const src = readFileSync(MOCK_DATA, 'utf8')
  const blk = src.match(/export const TASK_MATERIALS[\s\S]*?\n\}/)
  if (!blk) {
    fail('[黑名单豁免] 没抓到 TASK_MATERIALS 块——豁免无法建立，别当成"没有问题"')
    return out
  }

  const TASK_TYPE_RE = /^ {2}([a-z0-9_]+):\s*\[/
  const FIELD_RE =
    /^\s*\{\s*key:\s*'((?:[^'\\]|\\.)*)',\s*label:\s*'((?:[^'\\]|\\.)*)',\s*placeholder:\s*'((?:[^'\\]|\\.)*)'/

  let cur = null
  let parsed = 0
  for (const line of blk[0].split(/\r?\n/)) {
    const t = line.match(TASK_TYPE_RE)
    if (t) {
      cur = t[1]
      continue
    }
    const m = line.match(FIELD_RE)
    if (!m) continue
    if (!cur) {
      fail(`[黑名单豁免] 在任何任务类型之前就读到了材料字段，TASK_MATERIALS 结构变了：${line.trim()}`)
      return new Map()
    }
    out.set(`catalog.material.${cur}__${m[1]}.label`, m[2])
    out.set(`catalog.material.${cur}__${m[1]}.placeholder`, m[3])
    parsed++
  }

  // 逐字段数对拍：漏解析会让豁免范围变窄（表现为误报、很吵），但也说明
  // 源行的书写形态变了（D6 说这些行一个字不改），该停下来看，不该带病往下跑。
  const total = (blk[0].match(/\{\s*key:/g) || []).length
  if (parsed !== total) {
    fail(
      `[黑名单豁免] TASK_MATERIALS 有 ${total} 个字段，只解析出 ${parsed} 个——` +
        `源行的书写形态变了（D6 说这些行一个字不改），先确认源，别改这里的正则`,
    )
  }
  return out
}

/* ------------------------------------------------------------------ *
 * 3. 校验
 * ------------------------------------------------------------------ */

function validate(byLocale, wire, matDisplay) {
  // --- 情形 1：zh / en 文件名集合必须相等 ---
  const nameSets = Object.fromEntries(
    LOCALES.map((l) => [l, new Set(byLocale[l].map((f) => f.file))]),
  )
  for (const l of LOCALES) {
    if (l === SOURCE) continue
    for (const f of nameSets[SOURCE]) {
      if (!nameSets[l].has(f)) fail(`[文件名集] ${l}/ 缺文件 ${f}`)
    }
    for (const f of nameSets[l]) {
      if (!nameSets[SOURCE].has(f)) fail(`[文件名集] ${SOURCE}/ 缺文件 ${f}（${l}/ 里有）`)
    }
  }

  // --- 展平成完整 key ---
  /** locale -> Map<fullKey(含复数后缀), value> */
  const flat = {}
  for (const l of LOCALES) {
    const m = new Map()
    for (const { base, entries } of byLocale[l]) {
      for (const [k, v] of entries) {
        const full = `${base}.${k}`
        if (m.has(full)) fail(`[重复 key] ${l}: ${full}`)
        m.set(full, v)
      }
    }
    flat[l] = m
  }

  // --- 情形 5：段数 / 域 / 角色 ---
  for (const l of LOCALES) {
    for (const full of flat[l].keys()) {
      const lk = logicalKey(full)
      const segs = lk.split('.')
      if (segs.length < 3 || segs.length > 4) {
        fail(`[key 形状] ${l}: ${full} 是 ${segs.length} 段，只允许 3 或 4 段`)
        continue
      }
      if (segs.length === 4 && !ROLES.has(segs[3]) && !VARIANT_BLOCKS.has(segs[2])) {
        fail(
          `[角色] ${l}: ${full} 的第 4 段 "${segs[3]}" 不在角色闭集里。\n` +
            `        角色描述"这句话在界面上扮演什么角色"，不是它的内容。\n` +
            `        可用角色：${[...ROLES].join(' ')}\n` +
            `        若这几条是**同一句话的互斥变体**（如数量文案的多分支、一个按钮的多态），\n` +
            `        把第 3 段改成变体块名，块内叶子就不受约束：${[...VARIANT_BLOCKS].join(' ')}\n` +
            `        要加新角色或新变体块：交给 batch-0 改 scripts/i18n-gen.mjs，不要自造同义词。`,
        )
      }
    }
  }

  // --- 逻辑 key 聚合 ---
  /** locale -> Map<logicalKey, {vars:Set, slots:Set, variants:Set}> */
  const logical = {}
  for (const l of LOCALES) {
    const m = new Map()
    for (const [full, v] of flat[l]) {
      const lk = logicalKey(full)
      let rec = m.get(lk)
      if (!rec) m.set(lk, (rec = { vars: new Set(), slots: new Set(), variants: new Set() }))
      for (const x of varsOf(v)) rec.vars.add(x)
      for (const x of slotsOf(v)) rec.slots.add(x)
      rec.variants.add(full === lk ? '' : full.slice(lk.length))
    }
    logical[l] = m
  }

  // --- 情形 3：逻辑 key 集必须逐字相等 ---
  for (const l of LOCALES) {
    if (l === SOURCE) continue
    for (const k of logical[SOURCE].keys()) {
      if (!logical[l].has(k)) fail(`[缺译] ${l} 缺 key：${k}`)
    }
    for (const k of logical[l].keys()) {
      if (!logical[SOURCE].has(k)) fail(`[多余] ${l} 多出 key：${k}（${SOURCE} 侧没有）`)
    }
  }

  const eqSet = (a, b) => a.size === b.size && [...a].every((x) => b.has(x))

  for (const [k, src] of logical[SOURCE]) {
    for (const l of LOCALES) {
      if (l === SOURCE) continue
      const other = logical[l].get(k)
      if (!other) continue

      // --- 情形 2：插值变量名集合必须相等 ---
      if (!eqSet(src.vars, other.vars)) {
        fail(
          `[插值不一致] ${k}：${SOURCE}={${[...src.vars]}} ${l}={${[...other.vars]}}` +
            `（{{count}} 写成 {{num}} 这类拼写差异会让插值静默留空）`,
        )
      }

      // --- 富文本 slot 集合必须相等（否则 Trans 的 slots 类型两边对不上） ---
      if (!eqSet(src.slots, other.slots)) {
        fail(`[slot 不一致] ${k}：${SOURCE}=<${[...src.slots]}> ${l}=<${[...other.slots]}>`)
      }

      // --- 情形 4：带 count 的 key，非源语言侧必须有 _one 和 _other ---
      if (src.vars.has('count') && l !== SOURCE) {
        for (const need of ['_one', '_other']) {
          if (!other.variants.has(need)) fail(`[复数] ${l} 的 ${k} 缺变体 ${k}${need}`)
        }
      }
    }
  }

  // --- 情形 7：黑名单 ---
  for (const l of LOCALES) {
    for (const [full, v] of flat[l]) {
      if (/\bTODO\b|\bFIXME\b|\bxxx\b/i.test(v)) {
        fail(`[占位译文] ${l}: ${full} 里有 TODO/FIXME/xxx —— 拿不准的译文写进交付报告，不许留占位`)
      }
      if (v.includes('⟦')) {
        fail(`[缺译标记] ${l}: ${full} 的值里出现了 ⟦ —— 缺译标记是运行时产物，不该写进语料`)
      }
      // 定点豁免见上面 2b：zh 侧材料 overlay 的值只要逐字等于 mock-data 里
      // 同一字段的 label/placeholder，它就是"显示文案"而不是"被翻译的 wire key"。
      const isSourceMaterialDisplay = l === SOURCE && matDisplay.get(full) === v
      if (wire.has(v.trim()) && !isSourceMaterialDisplay) {
        fail(
          `[wire key] ${l}: ${full} 的值 "${v}" 是 wire contract（TASK_MATERIALS.key 或 stance_enum），` +
            `永不进 key 表。见契约 12.2。`,
        )
      }
      if (l !== SOURCE) {
        const srcVal = flat[SOURCE].get(full)
        if (srcVal !== undefined && srcVal === v && CJK.test(v) && !SAME_TEXT_EXEMPT.has(full)) {
          fail(
            `[未翻译] ${l}: ${full} 的值与 ${SOURCE} 侧逐字相同且含中文 —— 照抄中文不是译文。\n` +
              `        确实必须相同（比如后端的字面量比较凭据）：加进 SAME_TEXT_EXEMPT 并写清理由。`,
          )
        }
      }
    }
  }

  return { flat, logical }
}

/* ------------------------------------------------------------------ *
 * 4. 生成
 * ------------------------------------------------------------------ */

// 刻意不写 /* eslint-disable */：生成物如果触发了 lint 规则，那是**生成器**的问题，
// 应该改生成器而不是把警告关掉。关掉之后下一个人只会看到一份"永远干净"的生成物。
const BANNER = `/**
 * 【生成物 · 禁止手改】
 * 由 scripts/i18n-gen.mjs 生成。改资源文件后跑 \`npm run i18n:gen\`。
 * 手改这里 → \`npm run i18n:check\` 会红（它逐字节比对生成结果）。
 */
`

const ident = (base) => base.replace(/[^A-Za-z0-9_]/g, '_')

function genKeys(logicalSrc, byLocale) {
  const keys = [...logicalSrc.keys()].sort()
  const plain = keys.filter((k) => logicalSrc.get(k).vars.size === 0)
  const rich = keys.filter((k) => logicalSrc.get(k).slots.size > 0)

  const union = (list, empty) =>
    list.length === 0 ? empty : list.map((k) => `\n  | '${k}'`).join('')

  let out = BANNER
  out += `\n/** 全部可用的**逻辑 key**（不含复数后缀——后缀由运行时选，调用方永远不写）。 */\n`
  out += `export type MessageKey =${union(keys, ' never')}\n`
  out += `\n/** 无插值变量的 key。useDocumentTitle / tApiError 的形参用它。 */\n`
  out += `export type PlainMessageKey =${union(plain, ' never')}\n`
  out += `\n/** 值里带具名 slot 的 key，只有它们能进 <Trans>。 */\n`
  out += `export type RichMessageKey =${union(rich, ' never')}\n`

  out += `\n/**\n * 每条 key 需要的插值变量。漏传是编译错误。\n *\n * count 恒为 number —— 它驱动 Intl.PluralRules 选变体，传字符串会静默走非复数分支。\n * 其余变量是 string | number：这里没有能推断出"它一定是数字"的事实源，\n * 硬标成 number 会逼调用方写没有意义的转换。\n */\n`
  out += `export interface MessageVars {\n`
  for (const k of keys) {
    const vars = [...logicalSrc.get(k).vars].sort()
    const shape =
      vars.length === 0
        ? 'Record<string, never>'
        : `{ ${vars.map((v) => `${v}: ${v === 'count' ? 'number' : 'string | number'}`).join('; ')} }`
    out += `  '${k}': ${shape}\n`
  }
  out += `}\n`

  out += `\n/** 每条富文本 key 的 slot 名。少一个 / 多一个 / 拼错都是编译错误。 */\n`
  if (rich.length === 0) {
    out += `export type MessageSlots = Record<string, never>\n`
  } else {
    out += `export interface MessageSlots {\n`
    for (const k of rich) {
      out += `  '${k}': ${[...logicalSrc.get(k).slots].sort().map((s) => `'${s}'`).join(' | ')}\n`
    }
    out += `}\n`
  }

  // 文件清单只用于让 diff 上看得见"新增了哪个资源文件"，不参与类型。
  out += `\n/** 参与本次生成的资源文件（调试用，改动这行说明有人加/删了资源文件）。 */\n`
  out += `export const RESOURCE_FILES = [\n${byLocale[SOURCE]
    .map((f) => `  '${f.file}',`)
    .join('\n')}\n] as const\n`
  return out
}

function genLocaleIndex(locale, files) {
  let out = BANNER
  out += `\nimport type { Catalog } from '../../types'\n`
  for (const f of files) out += `import ${ident(f.base)} from './${f.base}'\n`
  out += `\nconst TABLES: Record<string, Record<string, string>> = {\n`
  for (const f of files) out += `  '${f.base}': ${ident(f.base)},\n`
  out += `}\n`
  out += `
// 完整 key = 文件名 + '.' + 文件里的 key。这条拼接规则是"文件名决定 owner"
// 那套并行分工的唯一实现处，改它等于改契约 4.1。
const merged: Catalog = {}
for (const ns of Object.keys(TABLES)) {
  const table = TABLES[ns]
  for (const k of Object.keys(table)) merged[\`\${ns}.\${k}\`] = table[k]
}

export default merged
`
  return out
}

function genRootIndex() {
  let out = BANNER
  out += `\nimport type { Locale } from '../locale'\nimport type { Catalog } from '../types'\n`
  out += `
/**
 * per-locale 动态 import 表。
 *
 * 两份语料合计约 2000 条，全量静态打包会让中文用户白背一份英文。
 * 做成动态 import 并在 createRoot 之前 await，Vite build 会自动注入
 * modulepreload 抵消额外往返。
 */
export const CATALOG_LOADERS: Record<Locale, () => Promise<Catalog>> = {
`
  for (const l of LOCALES) out += `  ${l}: () => import('./${l}/index.gen').then((m) => m.default),\n`
  out += `}\n`
  return out
}

/* ------------------------------------------------------------------ *
 * 5. 主流程
 * ------------------------------------------------------------------ */

const CHECK = process.argv.includes('--check')

const byLocale = {}
for (const l of LOCALES) byLocale[l] = await loadLocale(l)

const wire = wireStrings()
const matDisplay = materialDisplayStrings()
const { logical } = validate(byLocale, wire, matDisplay)

const outputs = [
  [join(I18N_DIR, 'keys.gen.ts'), genKeys(logical[SOURCE] ?? new Map(), byLocale)],
  [join(LOCALES_DIR, 'index.gen.ts'), genRootIndex()],
  ...LOCALES.map((l) => [join(LOCALES_DIR, l, 'index.gen.ts'), genLocaleIndex(l, byLocale[l])]),
]

const norm = (s) => s.replace(/\r\n/g, '\n')

/* ------------------------------------------------------------------ *
 * 5.1 目录 overlay 与后端事实源的一致性断言（契约 D5）
 *
 * locales/{zh,en}/catalog.{task_type,skill,mode}.ts 是 i18n-sync-catalog 的产物，
 * D5 明写它们**不许手写**：「手写必然漂移，而漂移的表现是"同一个任务类型在两个页面
 * 显示两个英文名"」。这里就是防它的那条断言——把应有内容重新算一遍，逐字节比。
 *
 * 两种模式下都比、也都不写：
 *   · 不写，是因为写盘是 i18n:sync-catalog 的职责，一个产物只能有一个生成者；
 *     i18n:gen 顺手写它会让"跑哪条命令"变得看运气。
 *   · 两种模式都比，是因为 overlay 和后端漂了的时候，keys.gen.ts 生成得再对也没意义：
 *     此时 errors 非空，下面的写盘分支自然不会执行，先修漂移再生成。
 * ------------------------------------------------------------------ */
const catalog = await buildCatalogOutputs()
for (const e of catalog.errors) fail(e)
for (const [path, content] of catalog.outputs) {
  const rel = path.slice(ROOT.length + 1).replace(/\\/g, '/')
  if (!existsSync(path)) {
    fail(`[目录 overlay] 缺 ${rel} —— 跑 \`npm run i18n:sync-catalog\``)
    continue
  }
  if (norm(readFileSync(path, 'utf8')) !== norm(content)) {
    fail(
      `[目录 overlay 漂移] ${rel} 与事实源（后端 catalog.en-US.json / mock-data 源常量）不一致。\n` +
        `        它是生成物，不许手写（契约 D5）。改文案要改事实源，然后跑 \`npm run i18n:sync-catalog\`。`,
    )
  }
}

if (CHECK) {
  // --- 情形 6：生成物与目录现状不一致（有人改了资源没跑 gen） ---
  for (const [path, content] of outputs) {
    const rel = path.slice(ROOT.length + 1).replace(/\\/g, '/')
    if (!existsSync(path)) {
      fail(`[生成物] 缺 ${rel} —— 跑 \`npm run i18n:gen\``)
      continue
    }
    if (norm(readFileSync(path, 'utf8')) !== norm(content)) {
      fail(`[生成物过期] ${rel} 与资源文件不一致 —— 跑 \`npm run i18n:gen\` 后提交`)
    }
  }
} else if (errors.length === 0) {
  for (const [path, content] of outputs) writeFileSync(path, content, 'utf8')
}

if (errors.length > 0) {
  console.error(`\ni18n:${CHECK ? 'check' : 'gen'} 失败，${errors.length} 个问题：\n`)
  for (const e of errors) console.error('  ✗ ' + e)
  console.error(
    '\n规则出处：docs/I18N_CONTRACT.md。拿不准的地方**停下来问**，不要自己定 —— ' +
      '这是 12 个 agent 并行时唯一安全的做法。\n',
  )
  process.exit(1)
}

const total = logical[SOURCE]?.size ?? 0
console.log(
  CHECK
    ? `i18n:check 通过 —— ${total} 条逻辑 key，${LOCALES.length} 种语言，${byLocale[SOURCE].length} 个资源文件。`
    : `i18n:gen 完成 —— ${total} 条逻辑 key，写了 ${outputs.length} 个生成物。`,
)
