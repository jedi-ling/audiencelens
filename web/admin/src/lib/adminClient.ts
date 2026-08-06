/**
 * 后台管理 API 客户端。
 *
 * 认证：X-Admin-Token 请求头，对应服务端 AL_ADMIN_TOKEN 环境变量。
 * 服务端未设置该变量时，所有请求返回 503（code: admin_disabled）。
 * 令牌只存本项目自己的 localStorage，与用户产品前端的登录态完全独立
 * （两个应用甚至可以部署在不同域名下）。
 */

import {
  ApiError,
  type AdminAuditLogEntry,
  type AdminCostStats,
  type AdminJobDetail,
  type AdminJobList,
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
  type AdminUserList,
  type ApiErrorCode,
  type CdkGenerateResult,
  type CdkList,
  type ListFilters,
  type PlanEditableField,
  type TestConnectionResult,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE as string) || ''
const ADMIN_TOKEN_KEY = 'al_admin.token'

export function getAdminToken(): string | null {
  return localStorage.getItem(ADMIN_TOKEN_KEY)
}

export function setAdminToken(token: string | null): void {
  if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token)
  else localStorage.removeItem(ADMIN_TOKEN_KEY)
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

  listUsers: (opts: { q?: string; limit?: number; offset?: number } = {}) => {
    const params = new URLSearchParams()
    if (opts.q) params.set('q', opts.q)
    if (opts.limit != null) params.set('limit', String(opts.limit))
    if (opts.offset != null) params.set('offset', String(opts.offset))
    const qs = params.toString()
    return request<AdminUserList>(`/api/admin/users${qs ? `?${qs}` : ''}`)
  },

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
}
