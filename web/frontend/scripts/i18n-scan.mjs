#!/usr/bin/env node
/**
 * 扫源码里**还没外化**的中文 UI 字符串。owner: batch-0。
 *
 *   node scripts/i18n-scan.mjs              全仓，按文件汇总
 *   node scripts/i18n-scan.mjs --list       逐条列出（file:line 可点击）
 *   node scripts/i18n-scan.mjs src/pages/AskPage.tsx   只看某几个文件
 *   node scripts/i18n-scan.mjs --max 0      有任何一条就非零退出（收尾时用）
 *
 * ══════════════════════════════════════════════════════════════════
 * 这个脚本的**第一要务是不误报中文注释**。
 *
 * 全仓 1885 行中文注释记录了大量"为什么这么写"的决策依据，是这个仓库最有
 * 价值的部分，一行都不许动（纪律 1）。一个会把注释报成"待外化文案"的扫描器
 * 比没有扫描器更危险：它会引导 agent 去改注释。
 *
 * 所以这里不用正则找中文，而是走一遍**字符级词法扫描**，把文件切成
 * 注释 / 字符串 / 代码 三种区域，注释区整段丢掉。
 * 剩下两种区域里的中文才算候选：
 *   - 字符串区 = 字面量（'…' "…" `…`）
 *   - 代码区里的中文 = JSX 文本节点（本仓没有中文标识符），也要外化
 * ══════════════════════════════════════════════════════════════════
 *
 * 已知边界（如实写出来，不要以为它是全知的）：
 *   1. 不做正则字面量识别。`/中文/` 这种写法会被当成代码区 → 报出来。本仓没有。
 *   2. 不判断字符串是不是真会渲染到界面上。console.log('中文…')、
 *      wire key、engine-prompt 都会被扫到——它们靠下面的 ALLOW 清单排除，
 *      清单是**逐条写理由**的，不是模式匹配。
 *   3. 它只能告诉你"这里还有中文"，不能告诉你"这句该用哪个 key"。
 */

import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs'
import { join, dirname, resolve, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..')
const SRC = join(ROOT, 'src')

const CJK = /[㐀-䶿一-鿿豈-﫿。，、；：？！“”‘’（）《》—…·]/

/**
 * console.log / warn / error 的第一个实参不算 UI 文案。
 *
 * 契约 6.11 明写：console 里的中文**不翻、不进 key 表**——它是给开发者看的，
 * 不是界面。不排除掉的话，12 个 agent 里一定有人去"外化"它，
 * 而那会让 ⟦missing:⟧ 相关的诊断信息本身也变成需要语料才能显示的东西。
 *
 * 只认第一个实参（紧跟左括号）。中文出现在后续实参里仍然会被报出来——
 * 宁可多报也不漏报。
 */
const CONSOLE_CALL = /console\.(log|warn|error|info|debug|trace)\(\s*$/

/** 整目录跳过。 */
const SKIP_DIRS = new Set([
  'node_modules',
  'dist',
  // 语料本身就该是中文。
  'locales',
])

/**
 * 逐条允许清单。**必须写理由**——没有理由的豁免过几个月就没人敢删了。
 *
 * 形态：{ file: 路径前缀（相对 web/frontend）, text?: 完整字符串, why: 理由 }
 * 只写 file 表示整文件豁免；带 text 表示只豁免那一条。
 */
const ALLOW = [
  {
    file: 'src/temp/',
    why: '死代码，tsconfig.app.json 已 exclude，不进类型检查也不进打包。本期只是不翻译它（契约 1.2）',
  },
  {
    file: 'src/lib/mock-data.ts',
    why: 'TASK_MATERIALS[].key 是 wire contract、stance_enum 是引擎聚类键、条目一行一条的格式被后端 parity 正则逐行匹配。源行一个字不改，英文走 overlay（契约 D6 / 12.2）',
  },
  {
    file: 'src/App.tsx',
    why: 'ChunkErrorBoundary 与 PageLoading **刻意不走 i18n**：i18n 初始化失败时它们是唯一还能显示的东西，走 i18n 就是白屏套白屏（契约 5.2）',
  },
  {
    file: 'src/components/I18nBootFailure.tsx',
    why: '同上——语料加载失败时它是唯一还能显示的东西，必须硬编码双语字面量，走 i18n 就是白屏套白屏（契约 5.2）',
  },
  {
    file: 'src/pages/landing/HeroScene.tsx',
    why: '128 个汉字全部在 GLSL 着色器源码的注释里，零 UI 字符串（契约 4.3）',
  },
  {
    file: 'src/components/Layout.tsx',
    text: '苏ICP备2025198057号',
    why: '法定 ICP 备案号，逐字符固定。工信部要求原样公示，翻译或改写都是违规',
  },
  {
    file: 'src/lib/apiClient.ts',
    why: '两条兜底 message 是前端自己写的中文，已用 ApiError.messageLang 如实标注语种，由 tApiError 决定显不显示（契约 D2）',
  },
  {
    file: 'src/i18n/',
    why: 'i18n 内核自身：注释与 ⟦missing:⟧ 标记的说明文字。语料在 locales/ 下，已整目录跳过',
  },
]

function allowedReason(rel, text) {
  for (const a of ALLOW) {
    if (!rel.startsWith(a.file)) continue
    if (a.text === undefined || a.text === text) return a.why
  }
  return null
}

/* ------------------------------------------------------------------ *
 * 词法扫描：把文件切成 注释 / 字符串 / 代码
 * ------------------------------------------------------------------ */

/**
 * @returns {{kind:'str'|'code', text:string, line:number}[]}
 *   注释区**不出现在返回值里**——这是本脚本存在的理由，别为了"顺便报一下"改它。
 */
function lex(src) {
  const out = []
  let i = 0
  let line = 1
  let codeStart = 0
  const n = src.length

  // 模板字符串的 ${} 嵌套深度栈：进 ${ 回到代码态，} 回到模板态
  const tplStack = []

  const flushCode = (end) => {
    if (end > codeStart) {
      const text = src.slice(codeStart, end)
      if (CJK.test(text)) out.push({ kind: 'code', text, line: lineAt(codeStart) })
    }
  }
  // 行号按需算（只在真有中文时），比全程计数便宜也更不容易错
  const lineAt = (pos) => {
    let l = 1
    for (let p = 0; p < pos; p++) if (src.charCodeAt(p) === 10) l++
    return l
  }

  while (i < n) {
    const c = src[i]

    // --- 注释：整段丢弃，连行号都不记 ---
    if (c === '/' && src[i + 1] === '/') {
      flushCode(i)
      while (i < n && src[i] !== '\n') i++
      codeStart = i
      continue
    }
    if (c === '/' && src[i + 1] === '*') {
      flushCode(i)
      i += 2
      while (i < n && !(src[i] === '*' && src[i + 1] === '/')) i++
      i += 2
      codeStart = i
      continue
    }

    // --- 字符串字面量 ---
    if (c === "'" || c === '"') {
      flushCode(i)
      const q = c
      const isConsole = CONSOLE_CALL.test(src.slice(Math.max(0, i - 40), i))
      const start = ++i
      while (i < n && src[i] !== q) {
        if (src[i] === '\\') i++
        // 单/双引号字面量不跨行；跨行说明我们把某个除号当引号了，止损退出
        if (src[i] === '\n') break
        i++
      }
      const text = src.slice(start, i)
      if (CJK.test(text) && !isConsole) out.push({ kind: 'str', text, line: lineAt(start) })
      i++
      codeStart = i
      continue
    }

    // --- 模板字符串 ---
    if (c === '`') {
      flushCode(i)
      i++
      let start = i
      while (i < n) {
        if (src[i] === '\\') {
          i += 2
          continue
        }
        if (src[i] === '`') break
        if (src[i] === '$' && src[i + 1] === '{') {
          const text = src.slice(start, i)
          if (CJK.test(text)) out.push({ kind: 'str', text, line: lineAt(start) })
          // 进入 ${ … } 里的代码：交回主循环处理（可能又有字符串/注释）
          i += 2
          tplStack.push(1)
          codeStart = i
          break
        }
        i++
      }
      if (tplStack.length > 0) continue
      const text = src.slice(start, i)
      if (CJK.test(text)) out.push({ kind: 'str', text, line: lineAt(start) })
      i++
      codeStart = i
      continue
    }
    if (c === '}' && tplStack.length > 0) {
      flushCode(i)
      tplStack.pop()
      i++
      // 回到模板串体：继续往后读到 ` 或下一个 ${
      let start = i
      while (i < n) {
        if (src[i] === '\\') {
          i += 2
          continue
        }
        if (src[i] === '`') break
        if (src[i] === '$' && src[i + 1] === '{') {
          const text = src.slice(start, i)
          if (CJK.test(text)) out.push({ kind: 'str', text, line: lineAt(start) })
          i += 2
          tplStack.push(1)
          start = -1
          break
        }
        i++
      }
      if (start !== -1) {
        const text = src.slice(start, i)
        if (CJK.test(text)) out.push({ kind: 'str', text, line: lineAt(start) })
        i++
      }
      codeStart = i
      continue
    }

    i++
  }
  flushCode(n)
  return out
}

/** 代码区里的中文 = JSX 文本节点。按行切开，去掉纯符号噪声。 */
function jsxTextRuns(chunk, baseLine) {
  const runs = []
  let line = baseLine
  for (const raw of chunk.split('\n')) {
    const hits = raw.match(/[^<>{}()[\];,=&|!?:+\-*/\n\t]*[㐀-䶿一-鿿豈-﫿][^<>{}()[\];,=]*/g)
    if (hits) {
      for (const h of hits) {
        const text = h.trim()
        if (text && CJK.test(text)) runs.push({ text, line })
      }
    }
    line++
  }
  return runs
}

/* ------------------------------------------------------------------ *
 * 主流程
 * ------------------------------------------------------------------ */

function walk(dir, acc) {
  for (const name of readdirSync(dir)) {
    if (SKIP_DIRS.has(name)) continue
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) walk(p, acc)
    else if (/\.(ts|tsx)$/.test(name) && !name.endsWith('.gen.ts')) acc.push(p)
  }
  return acc
}

const argv = process.argv.slice(2)
const wantList = argv.includes('--list')
const maxIdx = argv.indexOf('--max')
const max = maxIdx === -1 ? null : Number(argv[maxIdx + 1])
const explicit = argv.filter((a, k) => !a.startsWith('--') && argv[k - 1] !== '--max')

/** 显式参数可以是文件也可以是目录（目录就递归展开）。 */
function expand(p) {
  if (!existsSync(p)) return []
  return statSync(p).isDirectory() ? walk(p, []) : [p]
}

const files =
  explicit.length > 0 ? explicit.flatMap((p) => expand(resolve(ROOT, p))) : walk(SRC, [])

let total = 0
let allowed = 0
const perFile = []

for (const abs of files.sort()) {
  const rel = relative(ROOT, abs).replace(/\\/g, '/')
  const src = readFileSync(abs, 'utf8')
  const hits = []
  for (const region of lex(src)) {
    const runs =
      region.kind === 'str'
        ? [{ text: region.text.trim(), line: region.line }]
        : jsxTextRuns(region.text, region.line)
    for (const r of runs) {
      if (!r.text || !CJK.test(r.text)) continue
      const why = allowedReason(rel, r.text)
      if (why) {
        allowed++
        continue
      }
      hits.push({ ...r, kind: region.kind })
    }
  }
  if (hits.length > 0) {
    total += hits.length
    perFile.push({ rel, hits })
  }
}

perFile.sort((a, b) => b.hits.length - a.hits.length)

for (const { rel, hits } of perFile) {
  console.log(`${String(hits.length).padStart(4)}  ${rel}`)
  if (wantList) {
    for (const h of hits) {
      const preview = h.text.length > 60 ? h.text.slice(0, 57) + '…' : h.text
      console.log(`        ${rel}:${h.line}  [${h.kind}] ${preview}`)
    }
  }
}

console.log(
  `\n未外化中文 UI 字符串：${total} 条，分布在 ${perFile.length} 个文件。` +
    `（另有 ${allowed} 条命中允许清单，见脚本里的 ALLOW，每条都写了理由）`,
)
if (!wantList) console.log('加 --list 看逐条位置。')

if (max !== null && total > max) {
  console.error(`\n超过阈值：${total} > ${max}`)
  process.exit(1)
}
