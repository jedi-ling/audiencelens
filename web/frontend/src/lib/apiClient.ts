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
  type CreateReviewResponse,
  type HealthConfig,
  type HitRate,
  type Identity,
  type IntentResult,
  type Judgment,
  type KeyStatus,
  type LeaderboardEntry,
  type PersonaPack,
  type ReviewDetail,
  type ReviewMode,
  type TaskType,
  type UsageSummary,
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

  saveKey: (apiKey: string, provider = 'anthropic') =>
    request<{ provider: string; masked: string }>('/api/keys', {
      method: 'POST',
      body: JSON.stringify({ api_key: apiKey, provider }),
    }),

  deleteKey: (provider = 'anthropic') =>
    request<{ deleted: number }>(`/api/keys/${provider}`, { method: 'DELETE' }),

  // ---------------- 对话式入口：意图解析 ----------------

  parseIntent: (text: string) =>
    request<IntentResult>('/api/intent/parse', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  // ---------------- 上传 ----------------

  upload: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return request<{ filename: string; stored_as: string; size: number; text: string }>(
      '/api/uploads',
      { method: 'POST', body: fd },
    )
  },

  // ---------------- 评审（v2 异步链路）----------------

  createReview: (params: {
    task_type: TaskType
    artifact: { title?: string; materials: { type: string; text: string }[] }
    mode?: ReviewMode
    persona_pack?: PersonaPack
  }) =>
    request<CreateReviewResponse>('/api/v2/reviews', {
      method: 'POST',
      body: JSON.stringify({ mode: 'standard', persona_pack: 'game-core', ...params }),
    }),

  getReview: (id: string) => request<ReviewDetail>(`/api/v2/reviews/${id}`),

  getJob: (id: string) =>
    request<{ id: string; status: string; progress: number; error_message: string | null }>(
      `/api/jobs/${id}`,
    ),

  // ---------------- 用量 / 配额 ----------------

  usage: () => request<UsageSummary>('/api/usage'),

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
}

export { ApiError }
