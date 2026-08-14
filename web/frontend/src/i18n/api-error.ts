/**
 * 后端错误 → 界面文案。
 *
 * ⚠ **这是止血，不是解。**
 * 10 个 code 撑不起后端 174 个 raise 点（`bad_request` 一个码就覆盖 75 段不同中文），
 * 英文用户会看到大量「请求参数有误」这种没有信息量的粗译文。
 * 真解在后端补细粒度 code + 消息目录，**不要因为这层能跑就以为问题解决了**。
 * 裁决与理由见 docs/I18N_CONTRACT.md D2，欠债记在第 13 节第 1 条。
 *
 * 规则（契约 D2）：
 *   ui_lang === 'zh'  → 用后端 message（后端更具体）
 *   ui_lang !== 'zh'  → 按 error.<code> 出前端译文（10 条，粒度粗但语种正确），
 *                       后端中文原文降级成 detail（折叠 / title 属性）而不是丢弃
 *
 * 例外：后端若已带 message_lang 且正好等于当前 ui_lang，就直接用后端 message
 * ——那是「后端确实用这个语种说话」的诚实标注，比前端的粗译文更具体。
 * 本期后端只会给 "zh-CN" 这个常量（它不是协商结果，就是一句事实标注）。
 */

import { ApiError } from '@/lib/types'
import { getLocale, getHtmlLang } from './locale'
import { t } from './runtime'
import type { PlainMessageKey } from './keys.gen'

const tPlain = t as unknown as (key: PlainMessageKey) => string

/** error.api.* 里逐条对应 ApiErrorCode。code 是闭集，这里穷举，不做字符串拼接。 */
const CODE_KEY = {
  bad_request: 'error.api.bad_request',
  unauthorized: 'error.api.unauthorized',
  forbidden: 'error.api.forbidden',
  not_found: 'error.api.not_found',
  rate_limited: 'error.api.rate_limited',
  quota_exceeded: 'error.api.quota_exceeded',
  llm_key_missing: 'error.api.llm_key_missing',
  upstream_error: 'error.api.upstream_error',
  internal_error: 'error.api.internal_error',
  admin_disabled: 'error.api.admin_disabled',
} as const satisfies Record<ApiError['code'], PlainMessageKey>

export interface ApiErrorText {
  /** 给用户看的主文案。 */
  text: string
  /**
   * 后端原文，语种可能与界面不一致。
   * 有值时请放进折叠区 / title 属性，**不要与主文案并排显示**——
   * 英文界面上并排一句中文，用户会以为界面坏了。
   */
  detail?: string
}

/**
 * @param fallbackKey 不是 ApiError 时（网络断了、代码抛了 TypeError）用的文案。
 *   刻意必填：`e instanceof Error ? e.message : '出错了'` 这种写法会把
 *   `TypeError: x is not a function` 原样甩给用户，全站现在有 30+ 处。
 */
export function tApiErrorParts(e: unknown, fallbackKey: PlainMessageKey): ApiErrorText {
  const locale = getLocale()
  if (!(e instanceof ApiError)) {
    // 非 ApiError 的原始 message 一律不显示：它要么是浏览器的英文运行时报错，
    // 要么是我们自己的中文兜底串，两种都不该在英文界面上出现。
    if (import.meta.env.DEV && e instanceof Error) {
      console.error('[i18n/api-error] 非 ApiError，已用 fallbackKey 代替：', e)
    }
    return { text: tPlain(fallbackKey) }
  }

  const backendLang = e.messageLang
  if (backendLang !== undefined) {
    // 后端标了语种，就按标注走——这条分支不猜。
    // 语种对得上：用后端 message（它比 10 个粗 code 具体得多）。
    // 对不上：出前端译文，后端原文降级成 detail，绝不与界面语言混排。
    const matches = backendLang.toLowerCase() === getHtmlLang(locale).toLowerCase()
    return matches ? { text: e.message } : { text: tPlain(CODE_KEY[e.code]), detail: e.message }
  }

  // 后端没标语种（老响应，或 api/__init__.py 那套 {"detail": ...} 的第二套信封）。
  // 只能按 D2 的裁决走：zh 界面用后端 message，非 zh 界面用前端译文。
  // 这一步里"后端 message 是中文"是一个**假设**而不是事实——它正是
  // message_lang 这个字段存在的理由，也是它必须尽快铺满全部 raise 点的理由。
  return locale === 'zh'
    ? { text: e.message }
    : { text: tPlain(CODE_KEY[e.code]), detail: e.message }
}

/** 只要主文案时用这个。需要展示后端原文请用 tApiErrorParts。 */
export function tApiError(e: unknown, fallbackKey: PlainMessageKey): string {
  return tApiErrorParts(e, fallbackKey).text
}
