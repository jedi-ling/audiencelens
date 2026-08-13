/**
 * 日期 / 数字 / 字节 / 百分比 / 金额的统一出口。
 *
 * **本文件是全仓唯一允许调 toLocaleString / toLocaleDateString /
 * toLocaleTimeString / Intl.* 的地方**，由 eslint.config.js 的
 * no-restricted-syntax 钉死。
 *
 * 为什么必须收口：格式化要与 getLocale() 同源。散在各页的话会出现两种坏结果——
 * 硬编码 'zh-CN' 会让英文界面显示中文日期；省略 locale 参数会让日期跟浏览器走、
 * 与界面语言脱钩（用户把界面切成英文，日期还是 2026/8/14，且没人能解释）。
 * 现状里两种都有：硬编码三处、省略七处，见契约 6.5。
 *
 * 空值不在这里兜底：入参不接受 null/undefined。
 * 「created_at 是 null 的时候显示什么」是文案决定，属于页面 owner，
 * 在这里默默返回 '' 会让「没有时间」和「时间是 1970」在界面上长得一样。
 */

import { getIntlLocale } from './locale'

/* Intl 构造器不便宜（每次 new 都要查 CLDR），按 locale+选项缓存。 */
const cache = new Map<string, unknown>()

function memo<T>(tag: string, make: () => T): T {
  const k = `${getIntlLocale()}|${tag}`
  const hit = cache.get(k)
  if (hit !== undefined) return hit as T
  const made = make()
  cache.set(k, made)
  return made
}

type DateInput = string | number | Date

function toDate(v: DateInput, fnName: string): Date {
  const d = v instanceof Date ? v : new Date(v)
  if (Number.isNaN(d.getTime())) {
    // 后端给了个解析不出来的时间戳。DEV 直接炸出来，PROD 留可见痕迹——
    // 显示 "Invalid Date" 或空白都会被当成界面 bug，查半天查不到源头。
    if (import.meta.env.DEV) {
      throw new Error(`${fnName}: 无法解析的时间值 ${JSON.stringify(v)}`)
    }
    console.error(`[i18n/format] ${fnName}: 无法解析的时间值`, v)
    return new Date(0)
  }
  return d
}

/** 2026/8/14 · 2026-08-14 视地区而定。只有日期，没有时间。 */
export function formatDate(v: DateInput): string {
  return memo('date', () =>
    new Intl.DateTimeFormat(getIntlLocale(), { dateStyle: 'medium' }),
  ).format(toDate(v, 'formatDate'))
}

/** 只有时分。 */
export function formatTime(v: DateInput): string {
  return memo('time', () =>
    new Intl.DateTimeFormat(getIntlLocale(), { timeStyle: 'short' }),
  ).format(toDate(v, 'formatTime'))
}

/** 日期 + 时分。列表里的 created_at 用这个。 */
export function formatDateTime(v: DateInput): string {
  return memo('datetime', () =>
    new Intl.DateTimeFormat(getIntlLocale(), { dateStyle: 'medium', timeStyle: 'short' }),
  ).format(toDate(v, 'formatDateTime'))
}

/** 千分位。digits 给定时固定小数位。 */
export function formatNumber(v: number, digits?: number): string {
  const tag = digits === undefined ? 'num' : `num${digits}`
  return memo(tag, () =>
    new Intl.NumberFormat(getIntlLocale(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }),
  ).format(v)
}

const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const

/**
 * 字节数。
 * 单位符号（B/KB/MB）不翻译——它们是国际通用符号，中文界面上也写 MB。
 * 只有数字部分跟 locale 走（千分位与小数点）。
 */
export function formatBytes(bytes: number): string {
  let n = Math.abs(bytes)
  let i = 0
  while (n >= 1024 && i < BYTE_UNITS.length - 1) {
    n /= 1024
    i += 1
  }
  const digits = i === 0 ? 0 : n < 10 ? 1 : 0
  return `${formatNumber(bytes < 0 ? -n : n, digits)} ${BYTE_UNITS[i]}`
}

/**
 * 百分比。入参是**比值**（0.87），不是 87。
 * 传 87 进来会渲染成 8,700%——所以这里刻意不做「大于 1 就当成已经是百分数」
 * 的智能猜测：猜错的那次没有任何报错，只是数字大了 100 倍。
 */
export function formatPercent(ratio: number, digits = 0): string {
  return memo(`pct${digits}`, () =>
    new Intl.NumberFormat(getIntlLocale(), {
      style: 'percent',
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }),
  ).format(ratio)
}

/**
 * 美元金额。
 *
 * **不做货币换算**：total_cost_usd 恒为美元，这里只改千分位与小数点，货币符号恒 '$'。
 * 换算需要汇率事实源，我们没有——猜一个汇率就是假数据（纪律 3）。
 * 也不用 Intl 的 style:'currency'：它在 zh-CN 下会渲染成 "US$1.23"，
 * 而这个数字在账单页上要和后端返回的 usd 值逐位对得上。
 */
export function formatUsd(amount: number, digits = 2): string {
  return `$${formatNumber(amount, digits)}`
}

/** locale 感知排序。不许各页自己 localeCompare。 */
export function compareText(a: string, b: string): number {
  return memo('collator', () => new Intl.Collator(getIntlLocale())).compare(a, b)
}

/**
 * 复数类别。runtime.ts 的变体解析用它。
 *
 * 放在 format.ts 而不是 runtime.ts，只是为了守住「Intl.* 只出现在本文件」这条，
 * 让 grep 一次就能查全所有 locale 敏感的行为。
 */
export function pluralCategory(count: number): string {
  return memo('plural', () => new Intl.PluralRules(getIntlLocale())).select(count)
}
