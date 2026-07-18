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

export interface AdminTimeseriesPoint {
  date: string
  reviews_total: number
  reviews_completed: number
  reviews_failed: number
  cost_usd: number
}

export interface AdminTimeseries {
  days: number
  series: AdminTimeseriesPoint[]
}

export interface AdminHitRate {
  persona_id: string | null
  total_judgments: number
  verified: number
  pending_verification: number
  hit: number
  partial: number
  miss: number
  unknown: number
  hit_rate: number | null
  sample_size: number
  low_confidence: boolean
  note: string | null
}

export interface AdminLeaderboardEntry {
  persona_id: string
  sample_size: number
  hit_rate: number | null
  low_confidence: boolean
}

export interface AdminLedgerOverview {
  hit_rate: AdminHitRate
  persona_leaderboard: AdminLeaderboardEntry[]
}

export interface AdminAuditLogEntry {
  id: string
  action: string
  target: string | null
  detail: unknown
  created_at: string | null
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
  key: {
    provider: string
    model: string | null
    api_base: string | null
    masked: string
    last_used_at: string | null
  } | null
}

/** 非 Anthropic 服务商预设——与 web/frontend/src/lib/types.ts、src/runner/llm_client.py 同名表保持一致。 */
export interface OpenAICompatiblePreset {
  id: string
  name: string
  api_base: string
  model: string
}

export const OPENAI_COMPATIBLE_PRESETS: OpenAICompatiblePreset[] = [
  { id: 'openai', name: 'OpenAI', api_base: 'https://api.openai.com/v1', model: 'gpt-4o' },
  { id: 'deepseek', name: 'DeepSeek', api_base: 'https://api.deepseek.com', model: 'deepseek-chat' },
  { id: 'kimi', name: 'Kimi (月之暗面)', api_base: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
  { id: 'qwen', name: '通义千问', api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  { id: 'glm', name: '智谱 GLM', api_base: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4' },
  { id: 'ollama', name: 'Ollama 本地模型', api_base: 'http://localhost:11434/v1', model: 'llama3' },
]

export interface TestConnectionResult {
  connected: boolean
  model?: string
  sample?: string
  error?: string
}

// ---------- CDK 兑换码 ----------

export type CdkStatus = 'active' | 'disabled' | 'exhausted' | 'expired'

export interface CdkCode {
  id: string
  code: string
  credits: number
  max_uses: number
  used_count: number
  expires_at: string | null
  status: CdkStatus
  batch_id: string | null
  note: string | null
  created_at: string | null
}

export interface CdkList {
  total: number
  offset: number
  codes: CdkCode[]
}

export interface CdkGenerateResult {
  batch_id: string
  codes: string[]
  count: number
  credits: number
  max_uses: number
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

export interface AdminJobDetail extends AdminJob {
  payload: unknown
  started_at: string | null
}

export interface AdminJobList {
  total: number
  offset: number
  jobs: AdminJob[]
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

export interface AdminReviewDetail extends AdminReviewRow {
  persona_pack: string | null
  selected_personas: unknown
  report_json: Record<string, unknown> | null
  calibration: unknown
}

export interface AdminReviewList {
  total: number
  offset: number
  reviews: AdminReviewRow[]
}

/** 可编辑字段名——目前只放开价格/额度这三项，见 plan_service.OVERRIDABLE_PLAN_FIELDS */
export type PlanEditableField = 'price_usd_month' | 'reviews_per_day' | 'cost_usd_per_day'

export interface Plan {
  id: string
  name: string
  price_usd_month: number
  reviews_per_day: number
  cost_usd_per_day: number
}

export interface AdminPlan extends Plan {
  overridden_fields: PlanEditableField[]
  editable_fields: PlanEditableField[]
  env_default: Partial<Record<PlanEditableField, number>>
}

export interface ListFilters {
  status?: string
  userId?: string
  limit?: number
  offset?: number
}

// ---------- 用户管理 ----------

export interface AdminUser {
  id: string
  email: string
  display_name: string | null
  plan: string
  is_active: boolean
  created_at: string | null
  reviews_total: number
  cost_usd_total: number
}

export interface AdminUserList {
  total: number
  offset: number
  users: AdminUser[]
}

// ---------- 统计分析 ----------

export interface AdminTaskTypeStat {
  task_type: string
  total: number
  completed: number
  failed: number
  cost_usd: number
}

export interface AdminPersonaPackStat {
  persona_pack: string
  total: number
}

export interface AdminCostStats {
  days: number
  cost_by_source: Record<string, number>
  top_users: Array<{
    user_id: string
    email: string | null
    cost_usd: number
    records: number
  }>
}
