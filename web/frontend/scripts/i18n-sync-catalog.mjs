#!/usr/bin/env node
/**
 * 目录 overlay 生成器。owner: batch-2 前端接线，页面 agent 只读产物。
 *
 *   node scripts/i18n-sync-catalog.mjs            重新生成 6 个 overlay 资源文件
 *   node scripts/i18n-sync-catalog.mjs --check    只校验，不写盘；不一致就非零退出
 *
 * 它做的事只有一件：把**已经存在于别处的事实源**搬成 i18n 资源文件的形状。
 *
 *   locales/en/catalog.{task_type,skill,mode}.ts  ← web/backend/app/i18n/catalog.en-US.json
 *   locales/zh/catalog.{task_type,skill,mode}.ts  ← src/lib/mock-data.ts 的源常量
 *
 * 为什么必须是生成的、不许手写（契约 D5 原文）：
 *   「前端离线兜底那份英文不许手写，由 npm run i18n:sync-catalog 从后端
 *     catalog.en-US.json 生成，产物入库，i18n:check 断言它与后端文件一致。
 *     手写必然漂移，而漂移的表现是"同一个任务类型在两个页面显示两个英文名"。」
 * 断言挂在 scripts/i18n-gen.mjs 里（它 import 本文件的 buildCatalogOutputs），
 * 所以 `npm run i18n:check` 一条命令就同时卡住"资源没跑 gen"和"overlay 与后端漂了"。
 *
 * ── 三条不做的事，写下来免得下一个人当成遗漏 ──
 *
 * 1. **不生成 stance_labels。** 中文侧的立场标签**就是** stance_enum 本身
 *    （"加愿望单" / "值得推进" / "观望"），而 stance_enum 是 wire contract：
 *    i18n-gen 的黑名单（wireStrings）逐值禁止它进 key 表，进了当场红。
 *    英文标签的下发通道另有其人——见 locales/zh/enum.primary_stance.ts 的文件头：
 *    「它的英文显示标签由后端 stance_labels_en 下发（契约 D4）」。
 *    在这里造一份等于给同一批标签立第二个 owner，正是 D5 要防的那件事。
 * 2. **不生成评审模式的 name。** 后端 REVIEW_MODES 没有 name 字段，档位名的 owner 是
 *    前端 enum.mode_badge.*（catalog.en-US.json 的 _meta._review_mode_names 写明了）。
 *    所以模式这一节只有 desc。
 * 3. **不生成人格包名。** 它的 zh / en 事实源按 D5 表都在前端，是唯一事实源不是兜底，
 *    住在手写的 locales/{zh,en}/catalog.persona_pack.ts 里，不能由本脚本覆盖。
 *
 * ── zh 侧为什么取自 mock-data 而不是后端 ──
 *
 * D5 表里 TASK_TYPES / SKILLS / REVIEW_MODES 的 zh 事实源写的是"后端"，但后端的中文
 * 是 Python 字面量（services/__init__.py），前端离线时读不到。前端手上唯一的离线中文
 * 就是 mock-data.ts 的源常量，它也正是这三类目录在**中文界面**上今天显示的东西
 * （任务类型与评审模式两页都直接读它）。所以 zh 侧照抄源常量是唯一诚实的取值，
 * 而"照抄"必须由脚本做——手抄一次就会漂一次，catalog.ts 的 assertZhMatchesSource
 * 是运行期兜底，本脚本是构建期根治。
 *
 * ⚠ 已知且不由本脚本负责的一处口径差：技能的中文，后端
 * （services/__init__.py get_skill_types）与前端 mock-data 的 SKILLS[].description_zh
 * 措辞不同（后者额外写了 persona_generate "暂未接入评审流程"）。catalog.en-US.json
 * 的英文是**后端那份中文**的译文。技能页与创建评审页读的都是后端返回的行，
 * 所以中文界面看到的是后端那份、英文界面看到的是它的译文，两者成对；
 * 本文件生成的 zh 技能表只在"后端拉不到"时才有意义。要消掉这处差异，
 * 得改 mock-data 或后端，两边都不是本 agent 的文件。
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
const LOCALES_DIR = join(ROOT, 'src', 'i18n', 'locales')
const MOCK_DATA = join(ROOT, 'src', 'lib', 'mock-data.ts')
/** 后端英文事实源。路径写死而不是配置：它是契约 D4 指名的那一个文件，不该可配。 */
const BACKEND_CATALOG = resolve(ROOT, '..', 'backend', 'app', 'i18n', 'catalog.en-US.json')

/** 只有这三节走本脚本，其余目录的 owner 见文件头的"三条不做的事"。 */
const UNITS = ['task_type', 'skill', 'mode']

/** id 只允许 snake_case：它直接当 key 的第 3 段，出现连字符/大写会让 key 形状与全仓不一致。 */
const ID_RE = /^[a-z0-9_]+$/

/* ------------------------------------------------------------------ *
 * 1. 取两侧事实源
 * ------------------------------------------------------------------ */

/**
 * 读后端英文目录。
 *
 * 拿不到就报错、不跳过：跳过的表现是"卡口还在跑、还是绿的、但已经不查任何东西了"
 * （i18n-gen 的 wireStrings 对同一种失败写过同样的话）。
 */
function readBackendCatalog(errors) {
  if (!existsSync(BACKEND_CATALOG)) {
    errors.push(
      `[后端目录] 找不到 ${BACKEND_CATALOG.replace(/\\/g, '/')} —— ` +
        `它是契约 D4 指名的英文事实源，缺了就无法校验 overlay，不能当成"没有问题"。`,
    )
    return null
  }
  try {
    return JSON.parse(readFileSync(BACKEND_CATALOG, 'utf8'))
  } catch (e) {
    errors.push(`[后端目录] ${BACKEND_CATALOG.replace(/\\/g, '/')} 解析失败：${e.message}`)
    return null
  }
}

/**
 * 读前端源常量。
 *
 * 直接 import .ts（Node ≥22.6 的类型剥离），不做正则解析——理由与 i18n-gen 文件头
 * 那段一字不差：正则解析 TS 会在第一个多行字面量上悄悄漏掉条目，而漏掉的表现是
 * "这条 overlay 不存在 → 页面显示 ⟦missing:…⟧"，排查方向完全错。
 */
async function readMockData(errors) {
  if (!existsSync(MOCK_DATA)) {
    errors.push(`[源常量] 找不到 ${MOCK_DATA.replace(/\\/g, '/')}，zh 侧无法生成。`)
    return null
  }
  try {
    return await import(pathToFileURL(MOCK_DATA).href)
  } catch (e) {
    errors.push(`[源常量] 加载 src/lib/mock-data.ts 失败：${e.message}`)
    return null
  }
}

/* ------------------------------------------------------------------ *
 * 2. 把两侧对齐成 { unit -> { locale -> { key -> value } } }
 * ------------------------------------------------------------------ */

/**
 * 逐节比对 id 集。
 *
 * 这是本脚本真正的卡口：id 集一致意味着"每个条目两种语言都在"。少一个就是缺译，
 * 多一个就是有人只在一边加了条目。两种都必须红——静默生成一份缺条目的 overlay，
 * 表现是英文界面上某个任务类型显示 ⟦missing:…⟧，而没人知道是后端漏了还是前端漏了。
 */
function alignIds(unit, zhIds, enIds, errors) {
  for (const id of zhIds) {
    if (!ID_RE.test(id)) {
      errors.push(`[id 形状] ${unit} 的 "${id}" 不是 snake_case，不能直接当 key 的第 3 段。`)
    }
    if (!enIds.includes(id)) {
      errors.push(
        `[缺英文] ${unit} 的 "${id}" 在 src/lib/mock-data.ts 里有，` +
          `在后端 app/i18n/catalog.en-US.json 里没有 —— 后端补上这条，不要在前端手写。`,
      )
    }
  }
  for (const id of enIds) {
    if (!zhIds.includes(id)) {
      errors.push(
        `[缺中文] ${unit} 的 "${id}" 在后端 app/i18n/catalog.en-US.json 里有，` +
          `在 src/lib/mock-data.ts 里没有 —— 前端源常量落后于后端目录了。`,
      )
    }
  }
}

/** 值必须是非空字符串。空串会渲染成一片空白，比 ⟦missing:…⟧ 更难被发现。 */
function requireText(unit, id, role, value, side, errors) {
  if (typeof value !== 'string' || value.trim() === '') {
    errors.push(`[空文案] ${side} 的 ${unit}.${id}.${role} 是空的（实得 ${JSON.stringify(value)}）。`)
    return ''
  }
  return value
}

function buildTables(mock, backend, errors) {
  /** unit -> { zh: [[key, value]], en: [[key, value]] } */
  const tables = {}
  for (const unit of UNITS) tables[unit] = { zh: [], en: [] }

  // ---- 任务类型：name / description ----
  {
    const zhSrc = mock.TASK_TYPES
    const enSrc = backend.task_types ?? {}
    alignIds('task_type', zhSrc.map((x) => x.id), Object.keys(enSrc), errors)
    for (const tt of zhSrc) {
      tables.task_type.zh.push([`${tt.id}.label`, requireText('task_type', tt.id, 'label', tt.name, 'zh', errors)])
      tables.task_type.zh.push([`${tt.id}.desc`, requireText('task_type', tt.id, 'desc', tt.description, 'zh', errors)])
      const en = enSrc[tt.id]
      if (!en) continue
      tables.task_type.en.push([`${tt.id}.label`, requireText('task_type', tt.id, 'label', en.name, 'en', errors)])
      tables.task_type.en.push([`${tt.id}.desc`, requireText('task_type', tt.id, 'desc', en.description, 'en', errors)])
    }
  }

  // ---- 技能：name / description ----
  {
    const zhSrc = mock.SKILLS
    const enSrc = backend.skills ?? {}
    alignIds('skill', zhSrc.map((x) => x.type), Object.keys(enSrc), errors)
    for (const sk of zhSrc) {
      tables.skill.zh.push([`${sk.type}.label`, requireText('skill', sk.type, 'label', sk.name, 'zh', errors)])
      tables.skill.zh.push([`${sk.type}.desc`, requireText('skill', sk.type, 'desc', sk.description_zh, 'zh', errors)])
      const en = enSrc[sk.type]
      if (!en) continue
      tables.skill.en.push([`${sk.type}.label`, requireText('skill', sk.type, 'label', en.name, 'en', errors)])
      tables.skill.en.push([`${sk.type}.desc`, requireText('skill', sk.type, 'desc', en.description, 'en', errors)])
    }
  }

  // ---- 评审模式：只有 description（档位名的 owner 是 enum.mode_badge，见文件头）----
  {
    const zhSrc = mock.REVIEW_MODES
    const enSrc = backend.review_modes ?? {}
    alignIds('mode', zhSrc.map((x) => x.mode), Object.keys(enSrc), errors)
    for (const rm of zhSrc) {
      tables.mode.zh.push([`${rm.mode}.desc`, requireText('mode', rm.mode, 'desc', rm.description, 'zh', errors)])
      const en = enSrc[rm.mode]
      if (!en) continue
      tables.mode.en.push([`${rm.mode}.desc`, requireText('mode', rm.mode, 'desc', en.description, 'en', errors)])
    }
  }

  return tables
}

/* ------------------------------------------------------------------ *
 * 3. 渲染成资源文件
 * ------------------------------------------------------------------ */

/** 每节的来源说明，写进生成物的文件头——生成物被打开时最该回答的是"这是谁生成的、改哪儿"。 */
const UNIT_DOC = {
  task_type: {
    title: '任务类型的展示名与一句话描述',
    zh: 'src/lib/mock-data.ts 的 TASK_TYPES（源行受契约 D6 保护，一个字不改，这里只是照抄）',
    en: 'web/backend/app/i18n/catalog.en-US.json 的 task_types',
    note:
      'stance_enum / score_dimensions 不在这里：前者是 wire contract（永不翻译，' +
      '英文标签由后端 stance_labels_en 下发），后者是后端维度 id，本来就不是文案。',
  },
  skill: {
    title: '技能的展示名与描述',
    zh: 'src/lib/mock-data.ts 的 SKILLS（name / description_zh）',
    en: 'web/backend/app/i18n/catalog.en-US.json 的 skills',
    note:
      '⚠ 技能页与创建评审页读的是 **后端返回的行**（lib/skills.ts 的 SkillTruth），' +
      '不是这张表。这张表是"后端拉不到"时的离线兜底，且中文侧措辞与后端那份不完全一致——' +
      '详见 scripts/i18n-sync-catalog.mjs 文件头最后一段。',
  },
  mode: {
    title: '评审模式的描述',
    zh: 'src/lib/mock-data.ts 的 REVIEW_MODES[].description',
    en: 'web/backend/app/i18n/catalog.en-US.json 的 review_modes',
    note:
      '没有 name：后端 REVIEW_MODES 压根没有 name 字段，档位名（快速 / 标准 / 完整）的 ' +
      'owner 是 enum.mode_badge.*，在这里再给一份就是给同一个词立第二个 owner。',
  },
}

function render(unit, locale, entries) {
  const doc = UNIT_DOC[unit]
  const source = locale === 'zh' ? doc.zh : doc.en
  let out = `/**
 * 【生成物 · 禁止手改】${doc.title}（${locale}）。
 *
 * 由 scripts/i18n-sync-catalog.mjs 从下面这个事实源生成：
 *   ${source}
 * 改文案要改的是那个事实源，然后跑 \`npm run i18n:sync-catalog\` 重新生成并提交。
 * 手改这里 → \`npm run i18n:check\` 会红（它逐字节比对生成结果）。
 *
 * 手写禁令的出处是契约 D5：「手写必然漂移，而漂移的表现是"同一个任务类型在两个页面
 * 显示两个英文名"」。这份 overlay 的定位是**离线兜底**，不是事实源。
 *
 * ${doc.note}
 */
import type { Messages } from '@/i18n/types'

export default {
`
  for (const [k, v] of entries) {
    out += `  ${JSON.stringify(k)}: ${JSON.stringify(v)},\n`
  }
  out += `} satisfies Messages\n`
  return out
}

/* ------------------------------------------------------------------ *
 * 4. 对外入口：i18n-gen.mjs 靠它做 i18n:check 的断言
 * ------------------------------------------------------------------ */

/**
 * @returns {Promise<{ outputs: [string, string][], errors: string[] }>}
 *   outputs 是 [绝对路径, 应有内容]。调用方要么写盘（sync），要么逐字节比对（check）。
 */
export async function buildCatalogOutputs() {
  const errors = []
  const backend = readBackendCatalog(errors)
  const mock = await readMockData(errors)
  if (!backend || !mock) return { outputs: [], errors }

  const tables = buildTables(mock, backend, errors)
  const outputs = []
  for (const unit of UNITS) {
    for (const locale of ['zh', 'en']) {
      outputs.push([
        join(LOCALES_DIR, locale, `catalog.${unit}.ts`),
        render(unit, locale, tables[unit][locale]),
      ])
    }
  }
  return { outputs, errors }
}

/* ------------------------------------------------------------------ *
 * 5. 主流程（只有直接跑本文件时才执行；被 i18n-gen import 时不跑）
 * ------------------------------------------------------------------ */

const isMain = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))

if (isMain) {
  const CHECK = process.argv.includes('--check')
  const { outputs, errors } = await buildCatalogOutputs()
  const norm = (s) => s.replace(/\r\n/g, '\n')

  if (CHECK) {
    for (const [path, content] of outputs) {
      const rel = path.slice(ROOT.length + 1).replace(/\\/g, '/')
      if (!existsSync(path)) {
        errors.push(`[生成物] 缺 ${rel} —— 跑 \`npm run i18n:sync-catalog\``)
        continue
      }
      if (norm(readFileSync(path, 'utf8')) !== norm(content)) {
        errors.push(`[overlay 漂移] ${rel} 与事实源不一致 —— 跑 \`npm run i18n:sync-catalog\` 后提交`)
      }
    }
  } else if (errors.length === 0) {
    for (const [path, content] of outputs) writeFileSync(path, content, 'utf8')
  }

  if (errors.length > 0) {
    console.error(`\ni18n:sync-catalog${CHECK ? ' --check' : ''} 失败，${errors.length} 个问题：\n`)
    for (const e of errors) console.error('  ✗ ' + e)
    console.error('\n规则出处：docs/I18N_CONTRACT.md 的 D4 / D5。\n')
    process.exit(1)
  }

  console.log(
    CHECK
      ? `i18n:sync-catalog --check 通过 —— ${outputs.length} 个 overlay 与事实源一致。`
      : `i18n:sync-catalog 完成 —— 写了 ${outputs.length} 个 overlay 资源文件。`,
  )
}
