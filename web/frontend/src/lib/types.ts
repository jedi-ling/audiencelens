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
  // 通用产品向任务类型（不限游戏）
  | 'product_feedback_review'
  | 'pricing_page_review'
  | 'onboarding_review'
  // 创业项目评审（BP/路演/申报表）
  | 'pitch_review'

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
  | 'general-consumer'
  | 'startup-panel'

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
  | 'admin_disabled'

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
  /** 昵称。匿名身份为 null。 */
  display_name: string | null
  plan: string
  is_anonymous: boolean
}

export interface KeyInfo {
  provider: string
  model: string | null
  api_base: string | null
  masked: string
  last_used_at: string | null
}

export interface KeyStatus {
  key_mode: string
  server_key_available: boolean
  keys: KeyInfo[]
}

/** 非 Anthropic 服务商预设——都遵循 OpenAI 兼容协议，见 src/runner/llm_client.py 同名表。 */
export interface OpenAICompatiblePreset {
  id: string
  name: string
  api_base: string
  model: string
}

// 模型名核实于 2026-07-21（各厂商 API 文档/更新日志），见 docs/MAINTENANCE.md「4.3.5 服务商预设保鲜」
// 「服务商预设」一节。这类默认值有时效性——厂商换代快，过一阵子要再核一遍。
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

/** 评审材料——文字进模板正文，图片单独转多模态内容块（见 llm_client.py）。
 * 只有视觉能力模型才会真正"看"图；其余模型静默降级为纯文字，不报错阻断评审。 */
export type Material =
  | { type: 'text'; text: string }
  | { type: 'image'; image_data: string; filename?: string }

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
  /** 插入技能：只有 red_team_audience / audience_panel 真正影响评审 prompt 取向 */
  skill_type: 'red_team_audience' | 'audience_panel' | null
  /** 呼叫角色：用户点名想要的具体人格 id（落在 persona_pack 对应的包内） */
  matched_personas: string[]
  /** 长期评审项目：用户给的项目名，同名评审会在历史侧栏聚合成一组 */
  project_key: string | null
}

/** 报告出来后的真对话——persona_id 为 null 是"跟评审团整体聊"，
 * 给定则是"跟某个具体人格保持人设聊"，两条 thread 各自独立维护上下文。 */
export interface ChatMessage {
  id: string
  review_id: string
  persona_id: string | null
  role: 'user' | 'assistant'
  content: string
  /** 匿名用户追问：assistant 回复被裁成体验版，is_gated=true 时 content 已截断，
   * full_length 是完整回复的字符数，用来提示"还有多少内容登录才能看"。 */
  is_gated?: boolean
  full_length?: number | null
  created_at: string | null
}

export interface CreateReviewResponse {
  review_id: string
  job_id: string
  status: string
  /** 'byok' | 'server' —— 让用户知道这次花的是谁的钱 */
  key_source: 'byok' | 'server'
  /** 高级技能免费次数用完时的降级说明；null = 没降级。
   *  必须显示给用户——不吭声地少给一层能力，用户会以为产品本来就这样。 */
  skill_degraded: string | null
  websocket: string
}

/** GET /api/skill-quota —— 高级技能还剩几次免费体验 */
export interface SkillQuota {
  key_source: 'byok' | 'server'
  free_uses: number
  /** skill_type → 剩余次数；null = 不受限（BYOK / 匿名 / 机制关闭） */
  skills: Record<string, number | null>
}

export interface ReviewDetail {
  id: string
  task_type: TaskType
  mode: ReviewMode
  persona_pack: string | null
  selected_personas: string[] | null
  skill_type: string | null
  project_key: string | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  error_message: string | null
  created_at: string | null
  completed_at: string | null
  total_cost_usd: number
  input_tokens?: number
  output_tokens?: number
  report: ReviewReport | null
  calibration: unknown
}

/** 见 src/runner/aggregator.py aggregate_report()——不是一句话摘要，
 * 而是结构化的三段结论（在哪个环节形成，供 ReportPage/对话卡片各自取用）。 */
export interface ExecutiveSummary {
  primary_recommendation: string
  release_risk: string
  evidence_quality: string
}

export interface Disagreement {
  topic?: string
  persona_stances?: Array<{ persona_id?: string; stance?: string; evidence?: string }>
  resolution_suggestion?: string
}

export interface ReviewReport {
  executive_summary?: ExecutiveSummary
  consensus?: unknown
  major_disagreements?: Disagreement[]
  priority_fixes?: PriorityFix[]
  persona_notes?: PersonaNote[]
  information_gaps?: string[]
  cross_examination?: unknown
  simulation_notice?: string
  /** 匿名用户看到的是"体验版"：persona_notes 被裁成空，真实条数在 gated_counts 里。 */
  is_gated?: boolean
  gated_counts?: {
    priority_fixes_hidden: number
    persona_notes_hidden: number
  }
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

/** GET /api/plans 的套餐定义（plan_service.py 的镜像） */
export interface Plan {
  id: 'free' | 'pro' | 'team' | string
  name: string
  price_usd_month: number
  reviews_per_day: number
  cost_usd_per_day: number
}

export interface UsageSummary {
  quota_enabled: boolean
  /** plan=套餐日限额；credits=纯 CDK 次数制（每次评审消耗 1 次，用完即止） */
  quota_mode: 'plan' | 'credits'
  window: string
  reviews_used: number
  reviews_limit: number | null
  /** reviews_limit 是否被「邮箱未验证」压低了。由后端算，前端不要自己推：
   *  是否真被压还取决于 quota_enabled / quota_mode / 是否匿名，在前端重算必然走偏。 */
  reviews_limit_capped_unverified: boolean
  cost_usd_total: number
  cost_usd_on_server_key: number
  cost_usd_limit: number | null
  /** CDK 次数余额：credits 模式下这就是全部额度；plan 模式下是日限用完后的加量 */
  bonus_credits: number
  /** 累计烧掉的平台 token（输入+输出）。不按 24h 滚动，是终身量；只算平台垫付，不含 BYOK。
   *  配额关闭时也如实回报，方便用户随时知道自己用了多少。 */
  tokens_used: number
  /** 终身 token 上限；null = 不限制 */
  tokens_limit: number | null
  /** 你**一共**烧了多少 token（含 BYOK，终身不设窗）。与 tokens_used 语义不同：
   *  前者是"我方垫付了多少"（配额口径），这个是"你一共花了多少"（真实用量）。
   *  BYOK 用户的消耗全在 byok 上，只看 tokens_used 会永远是 0。 */
  tokens_used_all: number
  /** 24h 内真实评审次数（含 BYOK）。reviews_used 是配额口径，只算平台垫付。 */
  reviews_used_all: number
}

/** POST /api/cdk/redeem 的响应。匿名兑换（认证开启）会附带游客身份 token——
 * 前端必须 setToken 存下它，否则次数就找不回来了。 */
export interface RedeemCdkResult {
  credits_granted: number
  balance: number
  user_id: string
  token?: string
  guest?: boolean
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

export interface ValidationMetrics {
  completed_reviews: number
  feedback_count: number
  feedback_coverage: number | null
  useful_rate: number | null
  decision_change_rate: number | null
  fixes_suggested: number
  fixes_adopted: number
  adoption_rate: number | null
  hours_saved: number
  average_willingness_to_pay_usd: number | null
  total_model_cost_usd: number
  average_model_cost_usd: number | null
  cost_per_useful_review_usd: number | null
  cost_per_adopted_fix_usd: number | null
  by_task_type: Array<{
    task_type: string
    feedback_count: number
    useful_rate: number
    adoption_rate: number | null
    low_confidence: boolean
  }>
  top_adopted_fixes: Array<{ title: string; adoption_count: number }>
  low_confidence: boolean
  note: string | null
}

// ---------- WebSocket 事件 ----------

export type WsEventName =
  | 'review.started'
  | 'review.progress'
  | 'review.persona_started'
  | 'review.persona_completed'
  | 'review.persona_failed'
  | 'review.cross_exam_started'
  | 'review.cross_exam_completed'
  | 'review.aggregation_started'
  | 'review.aggregation_completed'
  | 'review.evaluation_completed'
  | 'review.cancelled'
  | 'review.completed'
  | 'review.failed'

export interface WsEvent<T = Record<string, unknown>> {
  event: WsEventName
  data: T
}

// 注：后台管理（Admin* 类型 + adminClient）已拆分到独立项目 web/admin/，
// 不再嵌入这个用户产品前端里。见 web/admin/src/lib/types.ts。

// ---------------- 对话持续化 ----------------
// 评审**之前**那段来回澄清。与 ReviewChatMessage（评审之后的追问）是两回事：
// 后者必须挂在某条 review 上，前者可以一条评审都还没有。

export interface ConversationSummary {
  id: string
  title: string | null
  /** 这段对话最终产出的评审（弱引用：删评审不会删掉对话本身） */
  review_id: string | null
  created_at: string | null
  /** 列表按它倒序。按 created_at 排会让老对话里的新消息沉底。 */
  updated_at: string | null
}

export interface StoredConversationMessage {
  id: string
  /** 服务端分配的顺序号。不能靠 created_at 排——同一次交互的问与答
   *  可能落在同一毫秒，会被随机颠倒成一答一问。 */
  seq: number
  role: 'user' | 'assistant' | 'system'
  content: string
  /** 卡片类消息（评审卡/确认卡/附件）的结构化载荷，重放时还原气泡形态用 */
  meta: Record<string, unknown> | null
  created_at: string | null
}

export interface ConversationDetail extends ConversationSummary {
  messages: StoredConversationMessage[]
}
