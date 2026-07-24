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

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
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
      | { filename: string; kind: 'text'; stored_as: string; size: number; text: string }
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
    request<{ review_id: string; overall_score: number; passed: boolean }>(
      `/api/evaluations/${reviewId}`,
      { method: 'POST' },
    ),

  getEvaluation: (reviewId: string) =>
    request<{ review_id: string; overall_score: number; passed: boolean }>(
      `/api/evaluations/${reviewId}`,
    ),

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
