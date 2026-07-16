/**
 * 后台管理 API 客户端 —— 独立于 apiClient.ts。
 *
 * 认证方式完全不同：普通用户走 Bearer JWT（或匿名），管理员走一个共享密钥
 * （X-Admin-Token 请求头，对应服务端 AL_ADMIN_TOKEN 环境变量），两者不应混用同一个
 * token 存储，所以单独一个 client 文件，而不是塞进 apiClient.ts 里做分支。
 *
 * 服务端未设置 AL_ADMIN_TOKEN 时，所有 /api/admin/* 请求返回 503
 * （code: admin_disabled）——前端据此提示"后台未启用"而不是"密码错误"。
 */

import {
  ApiError,
  type ApiErrorCode,
  type AdminJob,
  type AdminOverview,
  type AdminReviewRow,
  type AdminServerKeyStatus,
  type AdminSettingRow,
  type Plan,
} from './types'

const BASE = (import.meta.env.VITE_API_BASE as string) || ''
const ADMIN_TOKEN_KEY = 'al.admin_token'

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

export const adminApi = {
  overview: () => request<AdminOverview>('/api/admin/overview'),

  listSettings: () => request<{ settings: AdminSettingRow[] }>('/api/admin/settings'),

  setSetting: (key: string, value: unknown) =>
    request<{ key: string; value: unknown }>('/api/admin/settings', {
      method: 'PUT',
      body: JSON.stringify({ key, value }),
    }),

  resetSetting: (key: string) =>
    request<{ key: string; cleared: boolean }>(`/api/admin/settings/${key}`, { method: 'DELETE' }),

  serverKeyStatus: () => request<AdminServerKeyStatus>('/api/admin/server-key'),

  setServerKey: (apiKey: string, provider = 'anthropic') =>
    request<{ provider: string; masked: string }>('/api/admin/server-key', {
      method: 'PUT',
      body: JSON.stringify({ api_key: apiKey, provider }),
    }),

  deleteServerKey: (provider = 'anthropic') =>
    request<{ deleted: number }>(`/api/admin/server-key?provider=${provider}`, { method: 'DELETE' }),

  plans: () => request<{ plans: Plan[] }>('/api/admin/plans'),

  listJobs: (status?: string) =>
    request<{ jobs: AdminJob[] }>(`/api/admin/jobs${status ? `?status=${status}` : ''}`),

  listReviews: (status?: string) =>
    request<{ reviews: AdminReviewRow[] }>(`/api/admin/reviews${status ? `?status=${status}` : ''}`),
}
