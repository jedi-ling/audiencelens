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
    input_tokens_total: number
    output_tokens_total: number
    tokens_total: number
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
  input_tokens: number
  output_tokens: number
  tokens_total: number
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

// 模型名核实于 2026-07-21，见 docs/MAINTENANCE.md「4.3.5 服务商预设保鲜」一节。
export const OPENAI_COMPATIBLE_PRESETS: OpenAICompatiblePreset[] = [
  { id: 'openai', name: 'OpenAI', api_base: 'https://api.openai.com/v1', model: 'gpt-5.2' },
  { id: 'deepseek', name: 'DeepSeek', api_base: 'https://api.deepseek.com', model: 'deepseek-v4-pro' },
  { id: 'kimi', name: 'Kimi (月之暗面)', api_base: 'https://api.moonshot.cn/v1', model: 'kimi-k3' },
  { id: 'qwen', name: '通义千问', api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  { id: 'glm', name: '智谱 GLM', api_base: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-5' },
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
  input_tokens: number
  output_tokens: number
  tokens_total: number
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
  input_tokens_total: number
  output_tokens_total: number
  tokens_total: number
  /** 该用户单独的终身 token 上限；null = 跟随全局 AL_QUOTA_TOKENS_TOTAL */
  token_quota_total: number | null
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

// ---------- 运营健康 / 任务聚合 / 兑换记录 / 用户详情 ----------
//
// 与上面「统计分析」那批的区别：那批回答"跑了多少"，这批回答"跑得好不好、
// 出事时去哪儿看"。字段名与 app/api/admin.py 里对应端点的返回一一对应，
// 改名要两边一起改。

/** 分位数在样本为空时是 null，不是 0——0 会被图表画成一根真实存在的柱子。 */
export interface AdminPercentiles {
  sample_size: number
  p50: number | null
  p95: number | null
  avg?: number | null
  max: number | null
}

export interface AdminHealthPoint {
  date: string
  completed: number
  failed: number
  running: number
  /** null = 当天没有已结束的评审。不要在前端 ?? 0 —— 那会把空白天画成 0% 崩溃日 */
  success_rate: number | null
}

export interface AdminStuckJob extends AdminJob {
  stuck_minutes: number
}

export interface AdminHealth {
  days: number
  series: AdminHealthPoint[]
  totals: { completed: number; failed: number; success_rate: number | null }
  duration_seconds: AdminPercentiles
  stuck: { threshold_minutes: number; count: number; jobs: AdminStuckJob[] }
}

export interface AdminJobFailureReason {
  /** 归一化后的错误签名（UUID/数字已替换），用于把同类故障聚成一条 */
  signature: string
  count: number
  sample: string | null
}

export interface AdminJobStats {
  days: number
  by_status: Record<string, number>
  by_kind: Record<string, number>
  failure_reasons: AdminJobFailureReason[]
  runtime_seconds: AdminPercentiles
}

export interface AdminCdkRedemption {
  id: string
  code: string
  code_id: string
  note: string | null
  user_id: string
  /** null = 访客兑换（user_id 不在 users 表里）或用户已注销 */
  user_email: string | null
  credits: number
  /** credit_ledger 里对应的入账量。与 credits 对不上就是"兑了没到账" */
  credited_in_ledger: number | null
  created_at: string | null
}

export interface AdminCdkRedemptionList {
  total: number
  offset: number
  redemptions: AdminCdkRedemption[]
}

export interface AdminUsageBySource {
  key_source: string
  count: number
  cost_usd: number
  input_tokens: number
  output_tokens: number
}

/** 只有脱敏回显，永远没有密文——后端刻意不返回 key_ciphertext */
export interface AdminUserKeyRow {
  provider: string
  model: string | null
  api_base: string | null
  key_masked: string
  is_active: boolean
  created_at: string | null
  last_used_at: string | null
}

export interface AdminUserDetail {
  id: string
  email: string
  display_name: string | null
  plan: string
  is_active: boolean
  created_at: string | null
  token_quota_total: number | null
  reviews: {
    by_status: Record<string, number>
    total: number
    recent: AdminReviewRow[]
  }
  usage_by_key_source: AdminUsageBySource[]
  api_keys: AdminUserKeyRow[]
  credit_balance: number
  cdk_redemptions: Array<{ code: string; credits: number; created_at: string | null }>
}

/** /users 支持的排序列。聚合列（评审数/成本）刻意不在内——它们只在当前页内聚合，
 *  按它们排会得到"页内有序、跨页乱序"，比不能排更误导人。后端会 400。 */
export type AdminUserSortField = 'created_at' | 'email' | 'plan' | 'is_active'
