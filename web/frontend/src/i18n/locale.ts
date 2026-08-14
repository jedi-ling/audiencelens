/**
 * ui_lang 的单一事实源。
 *
 * 术语：这里管的是 **ui_lang**（界面文案语言，纯客户端状态，不上行），
 * 不是 report_lang（评审产出物语言，入队瞬间冻结、落库）、
 * 也不是 response_lang（后端系统文案语言，本期不做）。三者不共用变量。
 * 详见 docs/I18N_CONTRACT.md 第 0 节。
 *
 * 为什么真值放模块级变量而不是 React state / zustand store：
 * t() 必须能在 React 之外被调用——ReportPage.generateMarkdown 拼导出件、
 * api 层错误兜底、document.title 都在渲染树外面。只活在 hook 里的状态
 * 服务不了这三处。React 侧所需的全部就是 useSyncExternalStore(subscribe, getLocale)。
 */

import { useSyncExternalStore } from 'react'
import type { Catalog } from './types'
import { CATALOG_LOADERS } from './locales/index.gen'

export type Locale = 'zh' | 'en'

/** 代码里存在语料的全部语言。与 LOCALES（本次构建对用户开放的）是两回事。 */
export const ALL_LOCALES: readonly Locale[] = ['zh', 'en']

export const DEFAULT_LOCALE: Locale = 'zh'

/**
 * 本次构建对用户开放的语言，由构建期环境变量决定，默认只有 zh。
 *
 * 为什么要这个开关（契约 1.3）：法务页译文需要复核、落地页英文断言测试还没写、
 * 后端目录英文还没上线——这三件事都不是页面 agent 能独立完成的，但它们没完成
 * 之前，英文界面就是一个「看起来支持、实际上有洞」的东西。
 *
 * 自测英文：VITE_AL_LOCALES=zh,en npm run dev
 */
export const LOCALES: readonly Locale[] = parseLocalesEnv(
  (import.meta.env.VITE_AL_LOCALES as string | undefined) ?? 'zh',
)

function parseLocalesEnv(raw: string): readonly Locale[] {
  const parts = raw
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  const bad = parts.filter((p) => !(ALL_LOCALES as string[]).includes(p))
  if (bad.length > 0) {
    // 配置错了就当场炸，不静默丢弃。VITE_AL_LOCALES=zh,eng 这种 typo 如果被
    // 悄悄过滤掉，表现是「切换器里就是没有英文」，而没有任何人知道为什么。
    throw new Error(
      `VITE_AL_LOCALES 含未知语言：${bad.join(', ')}。可选值：${ALL_LOCALES.join(', ')}`,
    )
  }
  if (parts.length === 0) throw new Error('VITE_AL_LOCALES 不能为空')
  if (!parts.includes(DEFAULT_LOCALE)) {
    throw new Error(`VITE_AL_LOCALES 必须包含默认语言 ${DEFAULT_LOCALE}`)
  }
  return parts as Locale[]
}

/**
 * 每种语言的**自称**（endonym）。
 *
 * 语言选择器永远用自称显示，**不翻译、不进 key 表**：英文界面里把中文写成
 * "Chinese"，只认得「中文」两个字的用户就找不到自己的语言了——而找不到语言
 * 的用户恰恰是最需要这个控件的那批人。这是通行做法，不是本仓的发明。
 */
export const LOCALE_ENDONYM: Record<Locale, string> = { zh: '中文', en: 'English' }

/** <html lang> 用的 BCP-47 标签。与 Intl 用的不是同一张表，别合并。 */
const HTML_LANG: Record<Locale, string> = { zh: 'zh-CN', en: 'en' }

/**
 * Intl.* 用的 locale 标签。
 * en 这里是 en-US 而不是 en：日期顺序（M/D/Y vs D/M/Y）与货币写法都依赖地区，
 * 裸 'en' 会让 Intl 走 CLDR 的 en root，实测日期变成 D/M/Y——对一个以美元计价、
 * 面向北美独立开发者的产品是错的。<html lang> 那边不需要地区，所以两张表分开。
 */
const INTL_LOCALE: Record<Locale, string> = { zh: 'zh-CN', en: 'en-US' }

const STORAGE_KEY = 'al.locale'

let current: Locale = DEFAULT_LOCALE
const catalogs = new Map<Locale, Catalog>()
const listeners = new Set<() => void>()

export function getLocale(): Locale {
  return current
}

export function getIntlLocale(): string {
  return INTL_LOCALE[current]
}

export function getHtmlLang(locale: Locale = current): string {
  return HTML_LANG[locale]
}

/** 当前语言的语料。未初始化时返回 undefined——调用方必须显式处理，不许当空表。 */
export function getCatalog(): Catalog | undefined {
  return catalogs.get(current)
}

export function subscribe(fn: () => void): () => void {
  listeners.add(fn)
  return () => {
    listeners.delete(fn)
  }
}

async function loadCatalog(locale: Locale): Promise<void> {
  if (catalogs.has(locale)) return
  // 失败就往外抛。这里 catch 住会让「语料没加载成功」表现为「界面全是 ⟦missing:⟧」，
  // 用户看到一屏乱码而我们只在 console 里留了一行——正是纪律 2 禁止的形态。
  catalogs.set(locale, await CATALOG_LOADERS[locale]())
}

export async function setLocale(next: Locale): Promise<void> {
  if (next === current) return
  if (!LOCALES.includes(next)) {
    throw new Error(`语言 ${next} 未在本次构建中开放（VITE_AL_LOCALES）`)
  }
  await loadCatalog(next) // 失败就抛，不静默停在旧语言
  current = next
  localStorage.setItem(STORAGE_KEY, next)
  document.documentElement.lang = HTML_LANG[next]
  applyHead()
  listeners.forEach((fn) => fn())
}

/** React 视图。服务端快照与客户端同源——本站是纯客户端渲染，没有第二个真值。 */
export function useLocale(): Locale {
  return useSyncExternalStore(subscribe, getLocale, getLocale)
}

/**
 * 初始 ui_lang：?lang= > localStorage['al.locale'] > navigator.languages > zh。
 *
 * 三档都**不写回** localStorage，只有用户在切换器上点过（走 setLocale）才写。
 * 这样 localStorage 里有值 ⟺ 用户显式选过，区分得开「用户选过」和「我们猜的」。
 * 契约 5.1 只点名了第三档不写回；这里把规则推广到全部检测档，理由同构：
 * ?lang= 通常来自别人分享的链接，它表达的是分享者的语言而不是本人的偏好，
 * 写回去会让「点了一条英文链接 → 从此界面永久变英文」，而用户根本没做过这个选择。
 */
export function resolveInitialLocale(): Locale {
  const fromQuery = normalize(new URLSearchParams(window.location.search).get('lang'))
  if (fromQuery) return fromQuery

  const stored = normalize(safeReadStorage())
  if (stored) return stored

  for (const tag of navigator.languages ?? []) {
    const hit = normalize(tag)
    if (hit) return hit
  }
  return DEFAULT_LOCALE
}

function safeReadStorage(): string | null {
  // Safari 无痕模式下 localStorage 会抛。读不到就是读不到，按「没选过」处理。
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

/** 'zh-CN' / 'zh_Hans' / 'en-US' → Locale；映射不上返回 null（不猜）。 */
function normalize(tag: string | null | undefined): Locale | null {
  if (!tag) return null
  const primary = tag.toLowerCase().replace('_', '-').split('-')[0]
  const hit = ALL_LOCALES.find((l) => l === primary)
  if (!hit) return null
  // 语料里有、但本次构建没开放的语言，等同于没有——否则用户会看到一个
  // 切换器里根本不存在的语言，且切不回来。
  return LOCALES.includes(hit) ? hit : null
}

/**
 * 启动。main.tsx 必须 await 它再 createRoot——语料先到位，t() 才能保持同步函数，
 * 全站不需要 Suspense、不需要 async t。
 */
export async function initI18n(): Promise<void> {
  const next = resolveInitialLocale()
  await loadCatalog(next)
  current = next
  document.documentElement.lang = HTML_LANG[next]
  applyHead()
}

/**
 * <head> 同步。放在这里而不是 head.ts 里，是为了不让 locale.ts 依赖 head.ts
 * ——head.ts 需要 React（useDocumentTitle 是 hook），而 locale.ts 要能在
 * createRoot 之前跑。这里只做无 React 依赖的那一半。
 */
function applyHead(): void {
  const el = document.querySelector('meta[name="description"]')
  if (!el) return
  // 这里不用 t()：locale.ts → runtime.ts 是循环依赖里唯一还算干净的一条边，
  // 但 applyHead 会在 initI18n 里（模块求值刚结束时）被调用，走 t() 风险不必要。
  // 直接查表，缺了就不改——description 保持 index.html 里的静态中文兜底。
  const text = catalogs.get(current)?.['common.meta.description']
  if (text) el.setAttribute('content', text)
}
