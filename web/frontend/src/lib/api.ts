import type { Review, ReviewListItem, Report, Persona, PersonaPack, Preset, WSMessage, Example, ReviewModeConfig, TaskTypeDetail, ReviewResultData, SkillType, SkillDetail, EvaluationScorecard, EthicsReport } from './mock-data'
import { getToken, ApiError } from './apiClient'
import type { ApiErrorCode } from './types'
import { t } from '@/i18n/runtime'
import { getHtmlLang, getLocale } from '@/i18n/locale'
import type { PlainMessageKey } from '@/i18n/keys.gen'

/** t() 的重载要求带插值的 key 必须传 vars；这里只喂无插值的 key，收窄一下签名，
 *  免得每个调用点都写一个没有意义的空对象。同 i18n/api-error.ts 的写法。 */
const tPlain = t as unknown as (key: PlainMessageKey) => string

/** v1 链路统一出口：所有请求都带上登录态——
 *  后端按身份归属/裁剪数据，漏带 token 的调用会拿到匿名视角（见 fetchReport 的教训）。 */
function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const token = getToken()
  const headers = new Headers(init.headers)
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
  return fetch(input, { ...init, headers })
}

/* ------------------------------------------------------------------ *
 * 错误：把后端写清楚的原因原样交给用户
 *
 * 这里以前一律抛 `Failed to xxx: ${res.statusText}`，从不读响应体。后端
 * 花力气写的「PDF 文件已加密，暂不支持解析加密文档」「PDF 未提取到文字内容
 * （可能是纯图片扫描件，暂不支持 OCR）」「无法解析文件编码，请上传 UTF-8 或
 * GBK 编码的文本文件」全部烂在 body 里，用户只看到一句英文 statusText，
 * 完全不知道该怎么办——等于把"可自助修复的失败"降级成了"神秘失败"。
 *
 * 后端实际有两种错误体，都要认（不新造第三套，口径对齐 apiClient.ts）：
 *   1. AppError 链路      → {error:{code,message,detail}}  限流/配额/缺 key…
 *   2. HTTPException 链路 → {detail:"PDF 文件已加密…"}      v1 路由里直接 raise 的
 *      其中 422 参数校验是 {detail:[{loc,msg,type},…]}
 * 统一抛成 ApiError（apiClient.ts 已有的类型），页面既能拿 message 直接显示，
 * 也能按 code 分支（比如 llm_key_missing 引导去设置页）。
 * ------------------------------------------------------------------ */

/** HTTPException 没有业务 code，按状态码回填一个，让页面的 code 分支仍然可用 */
const STATUS_TO_CODE: Record<number, ApiErrorCode> = {
  400: 'bad_request',
  401: 'unauthorized',
  402: 'quota_exceeded',
  403: 'forbidden',
  404: 'not_found',
  428: 'llm_key_missing',
  429: 'rate_limited',
  502: 'upstream_error',
}

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    // FastAPI 422 校验错误：[{loc, msg, type}, …]
    const msgs = detail
      .map((d) =>
        d && typeof d === 'object' && typeof (d as { msg?: unknown }).msg === 'string'
          ? (d as { msg: string }).msg
          : null,
      )
      .filter((m): m is string => Boolean(m && m.trim()))
    // 分隔符跟界面语言走：全角分号出现在英文句子里是排版错误。
    if (msgs.length) return msgs.join(tPlain('error.fetch.separator'))
  }
  if (detail && typeof detail === 'object') {
    const m = (detail as { message?: unknown }).message
    if (typeof m === 'string' && m.trim()) return m
  }
  return null
}

/** 读响应体、翻译成 ApiError。fallbackKey 只在后端什么原因都没给时兜底。
 *
 *  第五个实参是 messageLang——**这条 message 是什么语种**的如实标注，
 *  由 tApiError 据此决定要不要把它显示在界面上（契约 D2）。三条分支各有各的答案：
 *    · AppError 信封  → 后端自己标的 message_lang；老响应没有这个字段就保持 undefined
 *    · HTTPException  → 自由文本，没有任何字段说它是什么语种，**不许猜**，留 undefined
 *    · 兜底那一句     → 是我们自己在前端拼的，语种就是当前 ui_lang，确定，如实标注
 *  不标注的后果不是"少一个字段"，是英文界面上混排中文而没有人发现。 */
async function toApiError(res: Response, fallbackKey: PlainMessageKey): Promise<ApiError> {
  let body: unknown = null
  try {
    const text = await res.text()
    body = text ? JSON.parse(text) : null
  } catch {
    body = null // 非 JSON（网关 HTML 错误页之类）：走 fallback，别把页面搞崩
  }

  const structured = (
    body as {
      error?: { code?: ApiErrorCode; message?: string; detail?: unknown; message_lang?: string }
    } | null
  )?.error
  if (structured?.message) {
    return new ApiError(
      res.status,
      structured.code ?? 'internal_error',
      structured.message,
      structured.detail,
      structured.message_lang,
    )
  }

  const detail = (body as { detail?: unknown } | null)?.detail
  const message = detailToMessage(detail)
  if (message !== null) {
    return new ApiError(res.status, STATUS_TO_CODE[res.status] ?? 'internal_error', message, detail)
  }
  return new ApiError(
    res.status,
    STATUS_TO_CODE[res.status] ?? 'internal_error',
    t('error.fetch.http_status', { message: tPlain(fallbackKey), status: res.status }),
    detail,
    getHtmlLang(getLocale()),
  )
}

/* ------------------------------------------------------------------ *
 * 评审列表分页
 *
 * 后端 GET /api/reviews 一直是 offset/limit 分页、默认 limit=20，而这里过去
 * 一个参数都不传：用户跑到第 21 次评审之后，旧评审在界面上就"消失"了，且没有
 * 任何提示——最难被发现的那类静默失败。现在：
 *   · fetchReviewsPage() 显式分页，并带回总数，供历史页做"加载更多 / 共 N 条"
 *   · fetchReviews() 保持"返回全部"的语义，内部翻页翻到底
 * ------------------------------------------------------------------ */

/** 历史页每次加载的条数 */
export const REVIEWS_PAGE_SIZE = 20
/** 后端对 limit 的硬上限（Query(..., le=100)），批量翻页按它走以少发几次请求 */
const REVIEWS_MAX_LIMIT = 100
/** 翻页保险丝：只防死循环（后端若返回异常数据），不是产品上限——
 *  正常情况下循环由 total / 短页两个条件先结束。 */
const REVIEWS_MAX_PAGES = 100

export interface ReviewsPage {
  items: ReviewListItem[]
  /** 该身份名下的评审总条数；后端没回 X-Total-Count 头时为 null（跨域未 expose 等） */
  total: number | null
  offset: number
  limit: number
  /** 还有没有下一页。total 已知时按 total 算，未知时退化成"这一页装满了就可能还有" */
  hasMore: boolean
  /** 后端说"这个列表要登录才有内容"（X-Requires-Login）。
   *
   *  多租户实例上，未登录访客共用同一个匿名身份，按它查出来的是**所有**
   *  未登录访客的评审。后端因此对这种身份返回空列表 + 这个头，而不是
   *  把别人的评审列给你看，也不是 401（侧栏在轮询，报错会把整页打成错误态）。
   *  前端据此显示"登录后查看历史"，否则用户只会看到历史莫名其妙空了。 */
  requiresLogin: boolean
}

export async function fetchReviewsPage(
  offset = 0,
  limit: number = REVIEWS_PAGE_SIZE,
): Promise<ReviewsPage> {
  const res = await authedFetch(`/api/reviews?offset=${offset}&limit=${limit}`)
  if (!res.ok) throw await toApiError(res, 'error.fetch.review_list')
  const items = (await res.json()) as ReviewListItem[]

  const raw = res.headers.get('X-Total-Count')
  const parsed = raw === null ? Number.NaN : Number(raw)
  const total = Number.isFinite(parsed) && parsed >= 0 ? parsed : null

  const hasMore = total === null ? items.length >= limit : offset + items.length < total
  const requiresLogin = res.headers.get('X-Requires-Login') === '1'
  return { items, total, offset, limit, hasMore, requiresLogin }
}

/**
 * 取全部评审（不分页的调用方用这个：/ask 左侧历史栏、review-store）。
 * 内部按 100 条一页翻到底——列表已是瘦身响应（无 artifact_bundle /
 * report_json / persona_outputs），几百条也只有几百 KB。
 */
export async function fetchReviews(): Promise<ReviewListItem[]> {
  return (await fetchReviewsAll()).items
}

/** 同 fetchReviews，但把"要登录才有内容"这个信号一并带出来。
 *  分开两个函数是为了不改动既有调用方的返回类型。 */
export async function fetchReviewsAll(): Promise<{
  items: ReviewListItem[]
  requiresLogin: boolean
}> {
  const all: ReviewListItem[] = []
  let offset = 0
  let requiresLogin = false
  for (let page = 0; page < REVIEWS_MAX_PAGES; page++) {
    const res = await fetchReviewsPage(offset, REVIEWS_MAX_LIMIT)
    if (res.requiresLogin) requiresLogin = true
    all.push(...res.items)
    if (!res.hasMore || res.items.length === 0) break
    offset += res.items.length
  }
  return { items: all, requiresLogin }
}

export async function fetchReview(id: string): Promise<Review> {
  const res = await authedFetch(`/api/reviews/${id}`)
  if (!res.ok) throw await toApiError(res, 'error.fetch.review')
  return res.json()
}

export async function fetchReport(reviewId: string): Promise<{ report_json: Report; report_markdown: string; calibration: unknown }> {
  const res = await authedFetch(`/api/reviews/${reviewId}/report`)
  if (!res.ok) throw await toApiError(res, 'error.fetch.report')
  return res.json()
}

export async function fetchPersonas(): Promise<Persona[]> {
  const res = await authedFetch('/api/personas')
  if (!res.ok) throw await toApiError(res, 'error.fetch.personas')
  return res.json()
}

export async function fetchPersonaPacks(): Promise<PersonaPack[]> {
  const res = await authedFetch('/api/personas/packs')
  if (!res.ok) throw await toApiError(res, 'error.fetch.persona_packs')
  return res.json()
}

export async function fetchExamples(): Promise<Example[]> {
  const res = await authedFetch('/api/examples')
  if (!res.ok) throw await toApiError(res, 'error.fetch.examples')
  return res.json()
}


export async function extractMaterials(taskType: string, file: File): Promise<{ title: string; materials: Record<string, string> }> {
  const formData = new FormData()
  formData.append('task_type', taskType)
  formData.append('file', file)
  const res = await authedFetch('/api/extract-materials', {
    method: 'POST',
    body: formData,
  })
  // 这个端点的错误最值得原样透出：加密 PDF / 纯图片扫描件 / 编码不对，
  // 后端都写明了用户该怎么办
  if (!res.ok) throw await toApiError(res, 'error.fetch.extract_materials')
  return res.json()
}

export async function deleteReview(id: string): Promise<void> {
  const res = await authedFetch(`/api/reviews/${id}`, { method: 'DELETE' })
  if (!res.ok) throw await toApiError(res, 'error.fetch.delete_review')
}


export async function fetchTaskTypes(): Promise<TaskTypeDetail[]> {
  const res = await authedFetch('/api/task-types')
  if (!res.ok) throw await toApiError(res, 'error.fetch.task_types')
  return res.json()
}

export async function fetchTaskType(taskType: string): Promise<TaskTypeDetail> {
  const res = await authedFetch(`/api/task-types/${taskType}`)
  if (!res.ok) throw await toApiError(res, 'error.fetch.task_types')
  return res.json()
}

export async function fetchReviewModes(): Promise<ReviewModeConfig[]> {
  const res = await authedFetch('/api/review-modes')
  if (!res.ok) throw await toApiError(res, 'error.fetch.review_modes')
  return res.json()
}


export async function fetchReviewResult(reviewId: string): Promise<ReviewResultData> {
  const res = await authedFetch(`/api/reviews/${reviewId}/result`)
  if (!res.ok) throw await toApiError(res, 'error.fetch.review_result')
  return res.json()
}

/** 后端 /api/skills 的真实响应形状（SkillTypeResponse）——之前这里声明成
 * SkillDetail 是错的，也从来没人调用过；技能中心页现在以它为"哪些技能可用"的事实源。 */
export async function fetchSkills(): Promise<{ skill_type: string; name: string; description: string }[]> {
  const res = await authedFetch('/api/skills')
  if (!res.ok) throw await toApiError(res, 'error.fetch.skills')
  return res.json()
}


export async function runEvaluation(reviewId: string): Promise<EvaluationScorecard> {
  const res = await authedFetch(`/api/evaluations/${reviewId}`, { method: 'POST' })
  if (!res.ok) throw await toApiError(res, 'error.fetch.run_evaluation')
  return res.json()
}

export async function fetchEvaluation(reviewId: string): Promise<EvaluationScorecard> {
  const res = await authedFetch(`/api/evaluations/${reviewId}`)
  if (!res.ok) throw await toApiError(res, 'error.fetch.evaluation')
  return res.json()
}

export async function fetchEthicsReport(reviewId: string): Promise<EthicsReport[]> {
  const res = await authedFetch(`/api/evaluations/${reviewId}/ethics`)
  if (!res.ok) throw await toApiError(res, 'error.fetch.ethics')
  return res.json()
}

