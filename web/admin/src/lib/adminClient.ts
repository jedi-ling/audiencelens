/**
 * 后台管理 API 客户端。
 *
 * 认证：X-Admin-Token 请求头。两种取值都认：
 *   1. 服务端 AL_ADMIN_TOKEN 环境变量原文（bootstrap/逃生舱）；
 *   2. /api/admin/auth/login 用具名账号（用户名+密码）换回的会话令牌——
 *      这是现在登录界面走的路径，能让审计日志落到具体人头上。
 * 服务端未设置 AL_ADMIN_TOKEN 时，所有请求返回 503（code: admin_disabled）。
 * 令牌只存本项目自己的 localStorage，与用户产品前端的登录态完全独立
 * （两个应用甚至可以部署在不同域名下）。
 */

import {
  ApiError,
  type AdminAuditLogEntry,
  type AdminCdkRedemptionList,
  type AdminCostStats,
  type AdminHealth,
  type AdminJob,
  type AdminJobDetail,
  type AdminJobList,
  type AdminJobStats,
  type AdminLedgerOverview,
  type AdminOverview,
  type AdminPersonaPackStat,
  type AdminPlan,
  type AdminReviewDetail,
  type AdminReviewList,
  type AdminServerKeyStatus,
  type AdminSettingRow,
  type AdminTaskTypeStat,
  type AdminTimeseries,
  type AdminUserDetail,
  type AdminUserList,
  type AdminUserSortField,
  type ApiErrorCode,
  type CdkGenerateResult,
  type CdkList,
  type ListFilters,
  type PlanEditableField,
  type TestConnectionResult,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE as string) || ''
const ADMIN_TOKEN_KEY = 'al_admin.token'
/** 登录成功时记下的用户名。**不是凭据**（凭据只有上面那个令牌），只用来在界面上
 *  回答一个问题："我正要停用的这个账号，是不是我自己？"没有它，管理员可以在
 *  毫无提示的情况下把自己踢下线。用静态主密钥（AL_ADMIN_TOKEN 原文）进来时
 *  没有用户名，此时返回 null，界面按"不知道是谁"处理、不硬猜。 */
const ADMIN_USERNAME_KEY = 'al_admin.username'

export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY)
}

export function setAdminToken(token: string | null): void {
  if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token)
  else {
    localStorage.removeItem(ADMIN_TOKEN_KEY)
    // 令牌没了，用户名也必须跟着没——留着的话下一个登进来的人会在
    // "这是你当前登录的账号"提示里看到上一个人的名字。
    localStorage.removeItem(ADMIN_USERNAME_KEY)
  }
}

export function getAdminUsername(): string | null {
  return localStorage.getItem(ADMIN_USERNAME_KEY)
}

export function setAdminUsername(username: string | null): void {
  if (username) localStorage.setItem(ADMIN_USERNAME_KEY, username)
  else localStorage.removeItem(ADMIN_USERNAME_KEY)
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getAdminToken()
  if (token) headers.set('X-Admin-Token', token)

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers })
  } catch {
    throw new ApiError(0, 'upstream_error', '无法连接后端服务，请确认服务已启动。')
  }

  const text = await res.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = null
  }

  if (!res.ok) {
    const err = (body as { error?: { code: ApiErrorCode; message: string } })?.error
    throw new ApiError(res.status, err?.code ?? 'internal_error', err?.message ?? `请求失败（HTTP ${res.status}）`)
  }
  return body as T
}

function listQuery(filters: ListFilters = {}): string {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.userId) params.set('user_id', filters.userId)
  if (filters.limit != null) params.set('limit', String(filters.limit))
  if (filters.offset != null) params.set('offset', String(filters.offset))
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export const adminApi = {
  login: (username: string, password: string) =>
    request<{ token: string; username: string }>('/api/admin/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  listAdminUsers: () =>
    request<
      { id: string; username: string; is_active: boolean; created_at: string; last_login_at: string | null }[]
    >('/api/admin/auth/users'),

  createAdminUser: (username: string, password: string) =>
    request<{ id: string; username: string }>('/api/admin/auth/users', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),

  deactivateAdminUser: (id: string) =>
    request<{ ok: boolean }>(`/api/admin/auth/users/${id}`, { method: 'DELETE' }),

  overview: () => request<AdminOverview>('/api/admin/overview'),

  timeseries: (days = 14) => request<AdminTimeseries>(`/api/admin/timeseries?days=${days}`),

  ledger: () => request<AdminLedgerOverview>('/api/admin/ledger'),

  listSettings: () => request<{ settings: AdminSettingRow[] }>('/api/admin/settings'),

  setSetting: (key: string, value: unknown) =>
    request<{ key: string; value: unknown }>('/api/admin/settings', {
      method: 'PUT',
      body: JSON.stringify({ key, value }),
    }),

  resetSetting: (key: string) =>
    request<{ key: string; cleared: boolean }>(`/api/admin/settings/${key}`, { method: 'DELETE' }),

  serverKeyStatus: (provider = 'anthropic') =>
    request<AdminServerKeyStatus>(`/api/admin/server-key?provider=${provider}`),

  setServerKey: (
    apiKey: string,
    provider = 'anthropic',
    opts: { model?: string; apiBase?: string } = {},
  ) =>
    request<{ provider: string; model: string | null; api_base: string | null; masked: string }>(
      '/api/admin/server-key',
      {
        method: 'PUT',
        body: JSON.stringify({ api_key: apiKey, provider, model: opts.model, api_base: opts.apiBase }),
      },
    ),

  /** 真实测一次已保存的平台 key——走评审真正会用的那条链路，不是摆设。 */
  testServerKey: (provider = 'anthropic') =>
    request<TestConnectionResult>(`/api/admin/server-key/test?provider=${provider}`, { method: 'POST' }),

  deleteServerKey: (provider = 'anthropic') =>
    request<{ deleted: number }>(`/api/admin/server-key?provider=${provider}`, { method: 'DELETE' }),

  // ---------- CDK 兑换码 ----------

  generateCdk: (params: {
    count: number
    credits: number
    max_uses?: number
    expires_in_days?: number
    note?: string
  }) =>
    request<CdkGenerateResult>('/api/admin/cdk/generate', {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  listCdk: (opts: { status?: string; limit?: number; offset?: number } = {}) => {
    const q = new URLSearchParams()
    if (opts.status) q.set('status', opts.status)
    if (opts.limit != null) q.set('limit', String(opts.limit))
    if (opts.offset != null) q.set('offset', String(opts.offset))
    const qs = q.toString()
    return request<CdkList>(`/api/admin/cdk${qs ? `?${qs}` : ''}`)
  },

  disableCdk: (codeId: string) =>
    request<{ id: string; disabled: boolean }>(`/api/admin/cdk/${codeId}/disable`, {
      method: 'PUT',
    }),

  plans: () => request<{ plans: AdminPlan[] }>('/api/admin/plans'),

  setPlanField: (planId: string, field: PlanEditableField, value: unknown) =>
    request<AdminPlan>(`/api/admin/plans/${planId}`, {
      method: 'PUT',
      body: JSON.stringify({ field, value }),
    }),

  resetPlanField: (planId: string, field: PlanEditableField) =>
    request<AdminPlan>(`/api/admin/plans/${planId}/${field}`, { method: 'DELETE' }),

  auditLog: (limit = 100) => request<{ entries: AdminAuditLogEntry[] }>(`/api/admin/audit-log?limit=${limit}`),

  listJobs: (filters: ListFilters = {}) => request<AdminJobList>(`/api/admin/jobs${listQuery(filters)}`),

  jobDetail: (id: string) => request<AdminJobDetail>(`/api/admin/jobs/${id}`),

  listReviews: (filters: ListFilters = {}) =>
    request<AdminReviewList>(`/api/admin/reviews${listQuery(filters)}`),

  reviewDetail: (id: string) => request<AdminReviewDetail>(`/api/admin/reviews/${id}`),

  deleteReview: (id: string) =>
    request<{ deleted: string }>(`/api/admin/reviews/${id}`, { method: 'DELETE' }),

  listUsers: (
    opts: {
      q?: string
      limit?: number
      offset?: number
      sort?: AdminUserSortField
      order?: 'asc' | 'desc'
    } = {},
  ) => {
    const params = new URLSearchParams()
    if (opts.q) params.set('q', opts.q)
    if (opts.limit != null) params.set('limit', String(opts.limit))
    if (opts.offset != null) params.set('offset', String(opts.offset))
    if (opts.sort) params.set('sort', opts.sort)
    if (opts.order) params.set('order', opts.order)
    const qs = params.toString()
    return request<AdminUserList>(`/api/admin/users${qs ? `?${qs}` : ''}`)
  },

  userDetail: (id: string) => request<AdminUserDetail>(`/api/admin/users/${id}`),

  /** token_quota_total 三态：不传=不改；>=0=设为该值（0=不限制）；-1=清除覆盖回落全局 */
  updateUser: (
    id: string,
    body: { plan?: string; is_active?: boolean; token_quota_total?: number },
  ) =>
    request<{
      id: string; email: string; plan: string; is_active: boolean
      token_quota_total: number | null
    }>(
      `/api/admin/users/${id}`,
      { method: 'PUT', body: JSON.stringify(body) },
    ),

  statsTaskTypes: () =>
    request<{ task_types: AdminTaskTypeStat[] }>('/api/admin/stats/task-types'),

  statsPersonaPacks: () =>
    request<{ persona_packs: AdminPersonaPackStat[] }>('/api/admin/stats/persona-packs'),

  statsCosts: (days = 30) => request<AdminCostStats>(`/api/admin/stats/costs?days=${days}`),

  // ---------- 运营健康 / 任务运维 / 兑换记录 ----------

  statsHealth: (days = 14, stuckMinutes?: number) => {
    const q = new URLSearchParams({ days: String(days) })
    if (stuckMinutes != null) q.set('stuck_minutes', String(stuckMinutes))
    return request<AdminHealth>(`/api/admin/stats/health?${q.toString()}`)
  },

  statsJobs: (days = 14) => request<AdminJobStats>(`/api/admin/stats/jobs?days=${days}`),

  /** 只能取消 queued。对 running 后端返回 400——进程内队列杀不掉运行中的线程。 */
  cancelJob: (id: string) =>
    request<AdminJob & { backend_cancelled: boolean }>(`/api/admin/jobs/${id}/cancel`, {
      method: 'POST',
    }),

  /** 把卡死的任务推到终态。不会真的停下线程，但能让统计与用户前端解锁。 */
  forceFailJob: (id: string) =>
    request<AdminJob & { review_updated: string | null }>(`/api/admin/jobs/${id}/force-fail`, {
      method: 'POST',
    }),

  cdkRedemptions: (
    opts: { code?: string; userId?: string; limit?: number; offset?: number } = {},
  ) => {
    const q = new URLSearchParams()
    if (opts.code) q.set('code', opts.code)
    if (opts.userId) q.set('user_id', opts.userId)
    if (opts.limit != null) q.set('limit', String(opts.limit))
    if (opts.offset != null) q.set('offset', String(opts.offset))
    const qs = q.toString()
    return request<AdminCdkRedemptionList>(`/api/admin/cdk/redemptions${qs ? `?${qs}` : ''}`)
  },
}
