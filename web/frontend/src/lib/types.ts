/**
 * 后端契约的 TypeScript 镜像。
 * 改动后端 schema 时，请同步这里 —— 这是前后端唯一的约定处。
 */

export type TaskType =
  | 'steam_page_review'
  | 'demo_first_play'
  | 'concept_review'
  | 'monetization_review'
  | 'looking_for_party_post'
  | 'update_announcement_review'
  | 'devlog_review'
  | 'kickstarter_review'
  | 'localization_review'
  | 'discord_community_review'

export type ReviewMode = 'quick' | 'standard' | 'full'

export type PersonaPack =
  | 'game-core'
  | 'competitive-esport'
  | 'family-casual'
  | 'indie-creative'
  | 'mobile-f2p'
  | 'vr-immersive'
  | 'accessibility'
  | 'educational-serious'

/** 后端统一错误契约：{ error: { code, message, detail? } } */
export type ApiErrorCode =
  | 'bad_request'
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'rate_limited'
  | 'quota_exceeded'
  | 'llm_key_missing'
  | 'upstream_error'
  | 'internal_error'

export class ApiError extends Error {
  code: ApiErrorCode
  status: number
  detail?: unknown

  constructor(status: number, code: ApiErrorCode, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }

  /** 缺 key —— 前端应把用户引导到设置页填写，而不是弹一个干瘪的报错 */
  get needsApiKey(): boolean {
    return this.code === 'llm_key_missing'
  }
}

export interface HealthConfig {
  env: string
  auth_enabled: boolean
  key_mode: 'byok' | 'managed' | 'hybrid'
  server_key_present: boolean
  quota_enabled: boolean
  ratelimit_enabled: boolean
  queue_backend: string
  ledger_enabled: boolean
  review_concurrency: number
}

export interface Identity {
  user_id: string
  email: string | null
  plan: string
  is_anonymous: boolean
}

export interface KeyInfo {
  provider: string
  masked: string
  last_used_at: string | null
}

export interface KeyStatus {
  key_mode: string
  server_key_available: boolean
  keys: KeyInfo[]
}

export interface IntentResult {
  task_type: TaskType | null
  mode: ReviewMode
  persona_pack: PersonaPack
  artifact_text: string
  confidence: number
  needs_clarification: boolean
  clarifying_question: string | null
  /** 'llm' 或 'heuristic' —— 如实声明用了哪档解析 */
  method: 'llm' | 'heuristic'
  candidates: string[]
}

export interface CreateReviewResponse {
  review_id: string
  job_id: string
  status: string
  /** 'byok' | 'server' —— 让用户知道这次花的是谁的钱 */
  key_source: 'byok' | 'server'
  websocket: string
}

export interface ReviewDetail {
  id: string
  task_type: TaskType
  mode: ReviewMode
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  error_message: string | null
  created_at: string | null
  completed_at: string | null
  total_cost_usd: number
  report: ReviewReport | null
  calibration: unknown
}

export interface ReviewReport {
  executive_summary?: string
  consensus?: unknown
  major_disagreements?: unknown[]
  priority_fixes?: PriorityFix[]
  persona_notes?: PersonaNote[]
  cross_examination?: unknown
  simulation_notice?: string
  [key: string]: unknown
}

export interface PriorityFix {
  title?: string
  severity?: 'low' | 'medium' | 'high' | 'critical'
  why_it_matters?: string
  suggested_fix?: string
}

export interface PersonaNote {
  persona_id: string
  persona_name?: string
  primary_stance?: string
  confidence?: number
  key_issues?: PriorityFix[]
}

export interface UsageSummary {
  quota_enabled: boolean
  window: string
  reviews_used: number
  reviews_limit: number | null
  cost_usd_total: number
  cost_usd_on_server_key: number
  cost_usd_limit: number | null
}

// ---------- 判断复利闭环 ----------

export type Verdict = 'hit' | 'miss' | 'partial' | 'unknown'

export interface Judgment {
  id: string
  review_id: string
  persona_id: string | null
  claim: string
  severity: string | null
  confidence: number | null
  predicted_at: string | null
  outcome: {
    verdict: Verdict
    source: string | null
    note: string | null
    verified_at: string | null
  } | null
}

export interface HitRate {
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
  /** 样本不足时为 true —— UI 必须如实展示，不能拿 3 个样本吹准确率 */
  low_confidence: boolean
  note: string | null
}

export interface LeaderboardEntry {
  persona_id: string
  sample_size: number
  hit_rate: number | null
  low_confidence: boolean
}

// ---------- WebSocket 事件 ----------

export type WsEventName =
  | 'review.started'
  | 'review.progress'
  | 'review.persona_completed'
  | 'review.completed'
  | 'review.failed'

export interface WsEvent<T = Record<string, unknown>> {
  event: WsEventName
  data: T
}
