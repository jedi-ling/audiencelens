/**
 * 类型化 API 客户端（v2 平台链路）—— 新代码请用这个。
 *
 * 与旧的 lib/api.ts 并存：旧文件服务于既有 11 个页面，
 * 迁移时逐页把 fetchXxx 换成 api.xxx 即可，不必一次性重写。
 *
 * 三件事在这里统一处理，页面不必各自操心：
 *   1. 认证：自动带 Bearer token（匿名形态下无 token 也能跑）
 *   2. 错误：把后端 {error:{code,message}} 统一抛成 ApiError，页面按 code 分支
 *      —— 尤其 llm_key_missing，应把用户引导去设置页填 key，而不是弹个干瘪报错
 *   3. 基址：VITE_API_BASE 配置；默认走 Vite 代理的同源 /api
 */

import {
  ApiError,
  type ApiErrorCode,
  type ChatMessage,
  type CreateReviewResponse,
  type HealthConfig,
  type HitRate,
  type Identity,
  type IntentResult,
  type Judgment,
  type KeyStatus,
  type LeaderboardEntry,
  type Material,
  type PersonaPack,
  type Plan,
  type RedeemCdkResult,
  type ReviewDetail,
  type ReviewMode,
  type TaskType,
  type TestConnectionResult,
  type UsageSummary,
  type ValidationMetrics,
  type Verdict,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE as string) || ''
const TOKEN_KEY = 'al.token'
const PENDING_REVIEWS_KEY = 'al.pending_reviews'
/** 本地待认领清单的条数上限——localStorage 不是数据库，超出丢最旧的 */
const PENDING_REVIEWS_MAX = 20

/* ------------------------------------------------------------------ *
 * 评估（8 维记分卡）的返回形状
 *
 * 这两个类型此前不存在：runEvaluation/getEvaluation 只声明了
 * { review_id, overall_score, passed }，而后端 EvaluationScorecardResponse
 * 一直还返回 results[] 与 critical_failures。类型撒谎的代价不是眼下报错——
 * 是后续把页面从 lib/api 的 v1 函数迁到这里的人，照类型判断"拿不到明细"，
 * 于是要么重复请求、要么干脆不渲染维度详情。字段对齐 web/backend
 * app/schemas/__init__.py 的 EvaluationResultResponse。
 * ------------------------------------------------------------------ */

export interface EvaluationDimensionResult {
  id: string
  review_id: string
  dimension: string
  score: number
  passed: boolean
  details: string
  /** ISO8601（后端 datetime 序列化结果） */
  evaluated_at: string
}

export interface EvaluationScorecardPayload {
  review_id: string
  overall_score: number
  passed: boolean
  results: EvaluationDimensionResult[]
  critical_failures: string[]
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

/* ------------------------------------------------------------------ *
 * 匿名评审的「待认领」清单
 *
 * 未登录时发起的评审落库 user_id="anonymous"，而后端归属校验是精确字符串
 * 比对。用户一登录 identity.user_id 变成真实 id，这条评审的所有路由立刻
 * 404 —— 页面上表现为"登录后报告凭空消失"。所以这里记下"这台浏览器匿名
 * 跑过哪些评审"，登录/注册成功后调 POST /api/auth/me/claim-reviews 认领。
 *
 * 边界（不粉饰）：只存 id 不存内容；清空浏览器数据 = 这些 id 永久失联，
 * 后端没有别的线索能把它们找回给谁——匿名本来就没有可信身份可绑。
 * ------------------------------------------------------------------ */

export function listPendingReviews(): string[] {
  try {
    const raw = localStorage.getItem(PENDING_REVIEWS_KEY)
    const parsed: unknown = raw ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return []
    return parsed.filter((x): x is string => typeof x === 'string' && x.length > 0)
  } catch {
    return [] // 手工改坏 / 旧格式：当作空清单，不让它把页面搞崩
  }
}

function writePendingReviews(ids: string[]): void {
  try {
    localStorage.setItem(PENDING_REVIEWS_KEY, JSON.stringify(ids.slice(0, PENDING_REVIEWS_MAX)))
  } catch {
    // 隐私模式 / 配额满：认领只是尽力而为的补救，存不下不该阻断评审本身
  }
}

/** 记下一条"匿名跑的评审"。已登录时什么都不做——那条评审本来就归属明确。 */
export function rememberPendingReview(id: string): void {
  if (!id || getToken()) return
  const current = listPendingReviews()
  if (current.includes(id)) return
  writePendingReviews([id, ...current])
}

export function forgetPendingReviews(ids: string[]): void {
  if (!ids.length) return
  const drop = new Set(ids)
  writePendingReviews(listPendingReviews().filter((id) => !drop.has(id)))
}

/**
 * 把本地清单里的匿名评审认领到当前账号名下。返回真正认领成功的 id。
 *
 * 未登录 / 清单为空时直接返回空数组（不发请求）。被拒绝的 id（不存在、或
 * 已属于别的账号）也从清单移除——留着只会每次登录都重试一遍必失败的请求。
 */
export async function claimPendingReviews(): Promise<string[]> {
  if (!getToken()) return []
  const pending = listPendingReviews()
  if (!pending.length) return []
  const res = await api.claimReviews(pending)
  forgetPendingReviews([...res.claimed, ...res.rejected])
  return res.claimed
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'upstream_error', '无法连接后端服务，请确认服务已启动。')
  }

  if (res.status === 204) return undefined as T

  const text = await res.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = null
  }

  if (!res.ok) {
    const err = (body as { error?: { code: ApiErrorCode; message: string; detail?: unknown } })
      ?.error
    throw new ApiError(
      res.status,
      err?.code ?? 'internal_error',
      err?.message ?? `请求失败（HTTP ${res.status}）`,
      err?.detail,
    )
  }
  return body as T
}

export const api = {
  // ---------------- 健康 / 身份 ----------------

  health: () => request<{ status: string; config: HealthConfig }>('/api/health'),

  me: () => request<Identity>('/api/auth/me'),

  register: (email: string, password: string, displayName?: string) =>
    request<{ token: string; user: { id: string; email: string; plan: string } }>(
      '/api/auth/register',
      { method: 'POST', body: JSON.stringify({ email, password, display_name: displayName }) },
    ),

  login: (email: string, password: string) =>
    request<{ token: string; user: { id: string; email: string; plan: string } }>(
      '/api/auth/login',
      { method: 'POST', body: JSON.stringify({ email, password }) },
    ),

  // ---------------- 邮箱验证 / 忘记密码 ----------------

  /** 给当前登录用户重新发一封验证邮件 */
  sendVerifyEmail: () =>
    request<{ sent: boolean; detail?: string }>('/api/auth/verify-email/send', { method: 'POST' }),

  confirmVerifyEmail: (token: string) =>
    request<{ verified: boolean; email: string }>('/api/auth/verify-email/confirm', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),

  /** 已登录改密码。成功会回一把**新令牌**：后端撤销了该用户所有旧会话
   *  （其他设备被踢下线），必须换上这把新的，否则本设备下一次请求就 401。
   *  调用方拿到后要立刻 setToken(r.token)。 */
  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ changed: boolean; token: string }>('/api/auth/password/change', {
      method: 'POST',
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  /** 改昵称。邮箱不在这里改——那要走"向新地址发验证信"的两步流程。 */
  updateProfile: (displayName: string) =>
    request<{ id: string; email: string; display_name: string }>('/api/auth/me', {
      method: 'PATCH',
      body: JSON.stringify({ display_name: displayName }),
    }),

  /** 申请密码重置链接。注册过与否都返回相同响应（后端防邮箱枚举）。 */
  forgotPassword: (email: string) =>
    request<{ sent: boolean; detail: string }>('/api/auth/password/forgot', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, newPassword: string) =>
    request<{ reset: boolean }>('/api/auth/password/reset', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    }),

  // ---------------- 数据自主权（导出 / 删号）----------------

  /** 导出我的全部数据（密钥只给掩码，不含明文） */
  exportMyData: () => request<Record<string, unknown>>('/api/auth/me/export'),

  /** 把登录前匿名跑的评审挂到当前账号下——不认领的话登录即 404（见文件顶部说明）。
   *  后端只放行"当前仍归属匿名桶"的评审，已属于别的账号的一律进 rejected。 */
  claimReviews: (reviewIds: string[]) =>
    request<{ claimed: string[]; rejected: string[]; claimed_count: number }>(
      '/api/auth/me/claim-reviews',
      { method: 'POST', body: JSON.stringify({ review_ids: reviewIds }) },
    ),

  /** 彻底删除我的内容与账号。confirm 必须是「删除我的账号」；已登录用户还要验密码。 */
  deleteMyAccount: (confirm: string, password?: string) =>
    request<{ deleted: boolean; detail: Record<string, number> }>('/api/auth/me/delete', {
      method: 'POST',
      body: JSON.stringify({ confirm, password: password || null }),
    }),

  // ---------------- BYOK Key ----------------

  getKeys: () => request<KeyStatus>('/api/keys'),

  saveKey: (
    apiKey: string,
    provider = 'anthropic',
    opts: { model?: string; apiBase?: string } = {},
  ) =>
    request<{ provider: string; model: string | null; api_base: string | null; masked: string }>(
      '/api/keys',
      {
        method: 'POST',
        body: JSON.stringify({ api_key: apiKey, provider, model: opts.model, api_base: opts.apiBase }),
      },
    ),

  deleteKey: (provider = 'anthropic') =>
    request<{ deleted: number }>(`/api/keys/${provider}`, { method: 'DELETE' }),

  /** 测连接：不传 apiKey 就测"当前已保存"的那把——测的是评审真正会走的链路，不是摆设。 */
  testKey: (opts: { apiKey?: string; provider?: string; model?: string; apiBase?: string } = {}) =>
    request<TestConnectionResult>('/api/keys/test', {
      method: 'POST',
      body: JSON.stringify({
        api_key: opts.apiKey,
        provider: opts.provider ?? 'anthropic',
        model: opts.model,
        api_base: opts.apiBase,
      }),
    }),

  // ---------------- 对话式入口：意图解析 ----------------

  parseIntent: (text: string) =>
    request<IntentResult>('/api/intent/parse', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  // ---------------- 上传（文本抽取成文字材料 / 图片转 data URI 供多模态） ----------------

  upload: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request<
      | { filename: string; kind: 'text'; size: number; text: string }
      | { filename: string; kind: 'image'; size: number; image_data: string }
    >('/api/uploads', { method: 'POST', body: fd })
  },

  // ---------------- 评审（v2 异步链路）----------------

  createReview: (params: {
    task_type: TaskType
    /** materials 两种形态引擎都原生支持：对话页的 {type:'text'|'image', ...}，
     *  以及 Wizard 的 {type: 字段名, description: 内容}（与 CLI 示例包同构） */
    artifact: { title?: string; materials: Array<Material | { type: string; description: string }> }
    mode?: ReviewMode
    persona_pack?: PersonaPack
    selected_personas?: string[]
    skill_type?: string | null
    project_key?: string | null
    /** 评审完成后自动运行 8 维质量评估 */
    enable_evaluation?: boolean
    /** 追加红队对抗视角提示（与 skill_type 独立可叠加） */
    enable_red_team?: boolean
  }) =>
    request<CreateReviewResponse>('/api/v2/reviews', {
      method: 'POST',
      body: JSON.stringify({ mode: 'standard', persona_pack: 'game-core', ...params }),
    }).then((res) => {
      // 匿名跑的评审在这里记下 id，登录后才认领得回来。写在唯一的创建出口上，
      // 两个入口（AskPage / review-store）就不会有哪个漏记。
      rememberPendingReview(res.review_id)
      return res
    }),

  /** 报告出来后追问——不传 personaId 是跟评审团整体聊，传了是跟该人格保持人设聊。
   * images：随消息附带的截图 data URI（支持视觉的模型直接"看"，其余降级纯文字）。 */
  sendReviewChat: (reviewId: string, message: string, personaId?: string | null, images?: string[]) =>
    request<{ reply: ChatMessage }>(`/api/v2/reviews/${reviewId}/chat`, {
      method: 'POST',
      body: JSON.stringify({
        message,
        persona_id: personaId ?? null,
        images: images && images.length ? images : null,
      }),
    }),

  getReviewChat: (reviewId: string, personaId?: string | null) =>
    request<{ messages: ChatMessage[] }>(
      `/api/v2/reviews/${reviewId}/chat${personaId ? `?persona_id=${encodeURIComponent(personaId)}` : ''}`,
    ),

  /** 手动对已完成评审运行 8 维质量评估（创建时没开 enable_evaluation 的补跑入口） */
  runEvaluation: (reviewId: string) =>
    request<EvaluationScorecardPayload>(`/api/evaluations/${reviewId}`, { method: 'POST' }),

  getEvaluation: (reviewId: string) =>
    request<EvaluationScorecardPayload>(`/api/evaluations/${reviewId}`),

  getReview: (id: string) => request<ReviewDetail>(`/api/v2/reviews/${id}`),

  getJob: (id: string) =>
    request<{ id: string; status: string; progress: number; error_message: string | null }>(
      `/api/jobs/${id}`,
    ),

  // ---------------- CDK 兑换码 ----------------

  /** 兑换 CDK。匿名兑换成功会返回游客 token——调用方负责 setToken 存下来。 */
  redeemCdk: (code: string) =>
    request<RedeemCdkResult>('/api/cdk/redeem', {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),

  // ---------------- 用量 / 配额 / 套餐 ----------------

  usage: () => request<UsageSummary>('/api/usage'),

  plans: () => request<{ plans: Plan[] }>('/api/plans'),

  // ---------------- 判断复利闭环 ----------------

  listJudgments: (opts: { reviewId?: string; onlyUnverified?: boolean } = {}) => {
    const q = new URLSearchParams()
    if (opts.reviewId) q.set('review_id', opts.reviewId)
    if (opts.onlyUnverified) q.set('only_unverified', 'true')
    const qs = q.toString()
    return request<{ judgments: Judgment[] }>(`/api/ledger/judgments${qs ? `?${qs}` : ''}`)
  },

  verifyJudgment: (id: string, verdict: Verdict, source = 'playtest', note?: string) =>
    request<{ judgment_id: string; verdict: string }>(`/api/ledger/judgments/${id}/verify`, {
      method: 'POST',
      body: JSON.stringify({ verdict, source, note }),
    }),

  hitRate: (personaId?: string) =>
    request<HitRate>(`/api/ledger/hit-rate${personaId ? `?persona_id=${personaId}` : ''}`),

  leaderboard: () => request<{ personas: LeaderboardEntry[] }>('/api/ledger/leaderboard'),

  validationMetrics: () => request<ValidationMetrics>('/api/validation/metrics'),

  submitReviewFeedback: (id: string, feedback: {
    useful: boolean
    decision_changed?: boolean
    fixes_suggested?: number
    fixes_adopted?: number
    hours_saved?: number
    willingness_to_pay_usd?: number
    note?: string
    adopted_fixes?: string[]
  }) => request<{ review_id: string; recorded: boolean }>(`/api/validation/reviews/${id}/feedback`, {
    method: 'POST',
    body: JSON.stringify(feedback),
  }),
}

export { ApiError }
