/**
 * 【生成物 · 禁止手改】
 * 由 scripts/i18n-gen.mjs 生成。改资源文件后跑 `npm run i18n:gen`。
 * 手改这里 → `npm run i18n:check` 会红（它逐字节比对生成结果）。
 */

import type { Locale } from '../locale'
import type { Catalog } from '../types'

/**
 * per-locale 动态 import 表。
 *
 * 两份语料合计约 2000 条，全量静态打包会让中文用户白背一份英文。
 * 做成动态 import 并在 createRoot 之前 await，Vite build 会自动注入
 * modulepreload 抵消额外往返。
 */
export const CATALOG_LOADERS: Record<Locale, () => Promise<Catalog>> = {
  zh: () => import('./zh/index.gen').then((m) => m.default),
  en: () => import('./en/index.gen').then((m) => m.default),
}
