/**
 * i18n 运行时本体：t / Trans / 缺译处理。
 *
 * 为什么自研而不引 react-i18next / lingui —— 见 docs/I18N_CONTRACT.md D1。
 * 一句话版本：现成库的核心契约 fallbackLng 的设计目的就是「缺了就悄悄用另一种
 * 语言」，产出的正是本仓纪律 2 明令禁止的「英文界面混中文、无痕迹」。
 * 要合规必须同时接管 fallbackLng + missingKeyHandler + parseMissingKeyHandler，
 * 改造完剩下的库价值只有插值。
 *
 * 本文件的三条硬规矩，改代码前先读：
 *   1. 缺译**永远不回落到另一种语言**。DEV 抛错，PROD 渲染 ⟦missing:…⟧ + console.error。
 *   2. 不做 source-as-key、不做 `?? key`、不做 `?? ''`。
 *   3. 消息串永远不进 innerHTML。富文本走 Trans 的具名 slot。
 */

import { createElement, Fragment, type ReactNode } from 'react'
import { getCatalog, getLocale, type Locale } from './locale'
import { pluralCategory } from './format'
import type { MessageVarValue } from './types'
import type { MessageKey, RichMessageKey, MessageVars, MessageSlots } from './keys.gen'

type Empty = Record<string, never>
type Vars = Record<string, MessageVarValue>

/**
 * 缺译标记。全仓（含后端 app/core/lang.py）统一为这一种形态，
 * 目的是**一条断言覆盖全链路**：`assert '⟦missing:' not in body`、一条 grep、
 * 一次截图肉眼可辨。两种形态就要两条断言，而漏写第二条的那天缺译就恢复隐身。
 * ⟦ U+27E6 / ⟧ U+27E7 在正常文案里绝不会出现。
 */
export function missingMarker(key: string, locale: Locale): string {
  return `⟦missing:${locale}:${key}⟧`
}

export class MissingMessageError extends Error {
  // 不用构造函数参数属性：tsconfig.app.json 开了 erasableSyntaxOnly
  // （为了让 Vite / Node 能纯剥离类型、不需要 TS 语义转换）。
  readonly key: string
  readonly locale: Locale

  constructor(key: string, locale: Locale) {
    super(`i18n 缺译：${missingMarker(key, locale)}`)
    this.name = 'MissingMessageError'
    this.key = key
    this.locale = locale
  }
}

function onMissing(key: string, locale: Locale): string {
  if (import.meta.env.DEV) throw new MissingMessageError(key, locale)
  console.error(`[i18n] 缺译 ${missingMarker(key, locale)}`)
  return missingMarker(key, locale)
}

/**
 * 变体解析：key + '_' + PluralRules.select(count) → key + '_other' → key。
 *
 * ⚠ 这是**同一语言内**的复数变体解析，不是跨语言回落，与「永不回落」不冲突。
 * zh 只有 other 一个复数类别，所以 zh 侧写裸 key 即可；en 侧带 count 的 key
 * 必须同时有 _one 和 _other（i18n:check 卡这条）。
 * 调用方永远只写逻辑 key，不写后缀（契约 D9）。
 */
function lookup(key: string, vars: Vars | undefined): string | undefined {
  const table = getCatalog()
  if (!table) {
    // 语料没加载就调 t()，说明有人在 initI18n() 之前渲染了东西。
    // 这不是缺译，是启动顺序错了，必须硬失败而不是返回标记——返回标记会让
    // 整屏 ⟦missing:⟧ 看起来像「译文没写全」，把人引向完全错误的方向。
    throw new Error(`i18n 尚未初始化就调用了 t('${key}')。main.tsx 必须先 await initI18n()。`)
  }
  const count = vars?.count
  if (typeof count === 'number') {
    return table[`${key}_${pluralCategory(count)}`] ?? table[`${key}_other`] ?? table[key]
  }
  return table[key]
}

const VAR_RE = /\{\{(\w+)\}\}/g

function interpolate(raw: string, vars: Vars | undefined, key: string, locale: Locale): string {
  if (!raw.includes('{{')) return raw
  return raw.replace(VAR_RE, (_m, name: string) => {
    const v = vars?.[name]
    if (v === undefined || v === null) {
      // 消息串要一个变量、调用方没给。类型层本来该拦住（MessageVars），
      // 走到这里说明生成物过期了。同样不许静默留空。
      if (import.meta.env.DEV) {
        throw new MissingMessageError(`${key}#${name}`, locale)
      }
      console.error(`[i18n] 插值缺参 ${missingMarker(`${key}#${name}`, locale)}`)
      return missingMarker(`${key}#${name}`, locale)
    }
    return String(v)
  })
}

/**
 * 取一条纯文本文案。
 *
 * 漏传 count 是编译错误；key 写错是编译错误（MessageKey 是 codegen 出来的字面量联合）。
 * 可以在 React 之外调用——导出件拼接、api 层错误兜底、document.title 都要用。
 */
export function t<K extends MessageKey>(
  key: K,
  ...args: MessageVars[K] extends Empty ? [] : [vars: MessageVars[K]]
): string {
  const locale = getLocale()
  const vars = args[0] as Vars | undefined
  const raw = lookup(key, vars)
  if (raw === undefined) return onMissing(key, locale)
  return interpolate(raw, vars, key, locale)
}

/* ------------------------------------------------------------------ *
 * 富文本：具名 slot，单层不嵌套
 *
 * 为什么不用 i18next 的 <Trans>：它按**位置索引**匹配（<0>/<1>），改一下 JSX
 * 顺序会静默错位——文案照样渲染、没人发现。具名 slot 的名字由 codegen 变成
 * MessageSlots 类型，少一个 / 多一个 / 拼错都是 tsc 错误。
 *
 * 单层不嵌套是刻意的限制：本仓 18 处内嵌全是一层，这个限制换来 tokenizer
 * 保持 50 行、行为完全可预测。需要嵌套时拆两条 key 或改设计，
 * 不许靠 i18n 层解决（契约 D13）。
 * ------------------------------------------------------------------ */

export type SlotRender = (children: ReactNode) => ReactNode

/** <name>…</name> | <br/> | 其余纯文本 */
const TOKEN_RE = /<(\w+)>([\s\S]*?)<\/\1>|<br\s*\/>/g

function render(
  raw: string,
  vars: Vars | undefined,
  slots: Record<string, SlotRender>,
  key: string,
  locale: Locale,
): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let i = 0
  TOKEN_RE.lastIndex = 0
  for (let m = TOKEN_RE.exec(raw); m !== null; m = TOKEN_RE.exec(raw)) {
    if (m.index > last) out.push(interpolate(raw.slice(last, m.index), vars, key, locale))
    if (m[1] === undefined) {
      out.push(createElement('br', { key: `br-${i++}` }))
    } else {
      const fn = slots[m[1]]
      const inner = interpolate(m[2], vars, key, locale)
      if (typeof fn !== 'function') {
        // 消息串里有 <terms>，调用方没给 terms 渲染器。类型层该拦住的，
        // 走到这里说明 keys.gen.ts 过期了。
        out.push(onMissing(`${key}#<${m[1]}>`, locale))
      } else {
        out.push(createElement(Fragment, { key: `s-${i++}` }, fn(inner)))
      }
    }
    last = m.index + m[0].length
  }
  if (last < raw.length) out.push(interpolate(raw.slice(last), vars, key, locale))
  return out
}

export function Trans<K extends RichMessageKey>(props: {
  k: K
  vars?: MessageVars[K]
  slots: { [S in MessageSlots[K] & string]: SlotRender }
}): ReactNode {
  const locale = getLocale()
  const vars = props.vars as Vars | undefined
  const raw = lookup(props.k, vars)
  if (raw === undefined) return onMissing(props.k, locale)
  return createElement(
    Fragment,
    null,
    ...render(raw, vars, props.slots as Record<string, SlotRender>, props.k, locale),
  )
}

/* 测试与校验脚本用的内部出口。业务代码不要用这两个。 */
export const __internal = { render, interpolate, lookup }
