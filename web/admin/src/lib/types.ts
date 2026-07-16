/**
 * 后端 /api/admin/* 契约的 TypeScript 镜像。
 * 与 web/frontend/src/lib/types.ts 里的同名类型保持字段一致——
 * 两边都是同一个后端 API 的消费者，schema 变了两边都要跟着改。
 */

export type ApiErrorCode =
  | 'bad_request'
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'rate_limited'
  | 'quota_exceeded'
  | 'upstream_error'
  | 'internal_error'
  | 'admin_disabled'

export class ApiError extends Error {
  code: ApiErrorCode
  status: number

  constructor(status: number, code: ApiErrorCode, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export interface AdminOverview {
  reviews: { total: number; by_status: Record<string, number> }
  usage_24h: {
    count: number
    cost_usd_total: number
    cost_usd_by_source: Record<string, number>
  }
  judgments: { total: number; verified: number }
  registered_users: number
  jobs_by_status: Record<string, number>
}

export interface AdminSettingRow {
  key: string
  label: string
  type: 'bool' | 'int' | 'float' | 'str'
  choices: string[] | null
  env_default: unknown
  effective_value: unknown
  overridden: boolean
}

export interface AdminServerKeyStatus {
  configured: boolean
  key: { provider: string; masked: string; last_used_at: string | null } | null
}

export interface AdminJob {
  id: string
  kind: string
  ref_id: string | null
  user_id: string | null
  status: string
  progress: number
  error_message: string | null
  created_at: string | null
  finished_at: string | null
}

export interface AdminReviewRow {
  id: string
  user_id: string | null
  task_type: string
  target_title: string | null
  mode: string
  status: string
  total_cost_usd: number
  error_message: string | null
  created_at: string | null
  completed_at: string | null
}

export interface Plan {
  id: string
  name: string
  price_usd_month: number
  reviews_per_day: number
  cost_usd_per_day: number
}
