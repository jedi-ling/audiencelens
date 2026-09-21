/**
 * 后端契约的 TypeScript 镜像。
 * 改动后端 schema 时，请同步这里 —— 这是前后端唯一的约定处。
 */

// 只用于 OPENAI_COMPATIBLE_PRESETS 的展示名 key（type-only import，运行时不产生依赖）。
import type { PlainMessageKey } from '@/i18n/keys.gen'

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
  // 后端 deps.py 对失效令牌发的码。它曾只存在于后端：前端类型没跟上时，
  // CODE_KEY[e.code] 查出 undefined → tPlain(undefined) 抛 MissingMessageError，
  // 把调用方 catch 里错误处理之后的所有语句全部炸掉——实测就是 /ask 侧栏
  // 两个"加载中"永远转圈的根因。
  | 'session_expired'

export class ApiError extends Error {
  code: ApiErrorCode
  status: number
  detail?: unknown
  /**
   * 后端 message 的语种（BCP-47），来自信封里的 `error.message_lang`。
   *
   * 它**不是协商结果**，就是一句诚实的事实标注：「这条 message 是中文」。
   * 本期后端恒给 "zh-CN"。undefined = 这个响应还没带这个字段（老后端 / 第二套
   * `{"detail": ...}` 信封），前端按"语种未知"处理，不许猜。
   *
   * 为什么必须有：没有它，前端无法判断拿到的 message 是不是英文，只能猜；
   * 猜错的表现是"英文界面混中文且没人发现"。见 docs/I18N_CONTRACT.md D2。
   */
  messageLang?: string

  constructor(
    status: number,
    code: ApiErrorCode,
    message: string,
    detail?: unknown,
    messageLang?: string,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
    this.messageLang = messageLang
  }

  /** 缺 key —— 前端应把用户引导到设置页填写，而不是弹一个干瘪的报错 */
  get needsApiKey(): boolean {
    return this.code === 'llm_key_missing'
  }
}

/** GET /api/health 的 config。
 *
 * 这个端点不鉴权，所以后端只回**前端真的要用的**四项，而不是所有非密钥配置。
 * 曾经还回过 env / ratelimit_enabled / queue_backend / ledger_enabled /
 * review_concurrency，前端一个都没消费——但它们组合起来是一张给攻击者的
 * 侦察表（限流关没关、配额关没关、有没有平台密钥）。详见 config.sanitized()。
 *
 * 想加字段前先问：前端真的会读它吗？读不到的字段不该出现在公开响应里。
 * 后端有 test_health_config_parity 守着这两边一致。 */
export interface HealthConfig {
  auth_enabled: boolean
  key_mode: 'byok' | 'managed' | 'hybrid'
  server_key_present: boolean
  quota_enabled: boolean
  /** QQ 登录是否已配齐（APP ID / APP KEY / 回调地址三项）。
   *  为 false 时不画那个按钮——画了点进去必然失败。 */
  qq_login_enabled: boolean
}

/** GET /api/v2/shared/{token} 的响应——公开只读视图。
 *
 *  这个类型就是后端 share_service.to_public_dict 白名单的镜像：**它没有
 *  user_id、没有邮箱、没有费用与 token 数、没有 artifact_bundle**。
 *  往这里加字段之前先确认后端真的会给，且那个字段确实可以给陌生人看。 */
export interface SharedReport {
  task_type: string
  mode: string
  target_title: string | null
  persona_pack: string | null
  selected_personas: string[] | null
  skill_type: string | null
  created_at: string | null
  completed_at: string | null
  shared_at: string | null
  report: unknown
  calibration: unknown
}

export interface UploadConfig {
  allowed_ext: string[]
  allowed_image_ext: string[]
  max_bytes: number
  max_image_bytes: number
}

export interface Identity {
  user_id: string
  email: string | null
  /** 昵称。匿名身份为 null。 */
  display_name: string | null
  plan: string
  is_anonymous: boolean
  /** 游客账号（邮箱是合成的、随时可能清缓存丢失）——is_anonymous 分不出
   *  "共享匿名桶"和"已铸造但没绑定的游客"，报告页的绑邮箱提示条要靠这个字段。 */
  is_guest: boolean
  /** 'qq' | 'email' | null —— 这个账号当初是怎么进来的，用来在昵称旁标一个
   *  「QQ 登录」/「邮箱登录」。null = 游客身份还没绑定任何登录方式，
   *  这时候不该硬贴"邮箱登录"（压根没有邮箱）。 */
  login_provider: 'qq' | 'email' | null
}

/* ------------------------------------------------------------------ *
 * 身份判定的三个谓词
 *
 * 为什么必须收在这里而不是各页面自己写 `identity.is_anonymous` / `is_guest`：
 * 后端把 **QQ 开的号也标成 is_guest=true**（它确实没有密码、没有真邮箱），
 * 于是两种最自然的写法都会出错：
 *   - 只看 is_anonymous  → 铸造出来的游客被当成正式账号，登录页把他弹走，
 *     他再也回不到登录页去登自己的真账号，唯一出路是登出——而登出会丢掉
 *     游客 token，连带丢掉他的评审与剩余次数。
 *   - 只看 is_guest      → QQ 用户被当成"清缓存就永久丢失"的临时身份，
 *     界面会对他说一句不成立的狠话（他随时能再用 QQ 登回来）。
 * 判据统一成"有没有一条能再登回来的路"，也就是 login_provider。
 * ------------------------------------------------------------------ */

/** 铸造出来的游客：有 user_id、有额度、有评审，但整条身份链只挂在这台浏览器的
 *  token 上——清缓存 / 换设备就永久找不回来。QQ 账号**不算**：它能再登回来。 */
export function isMintedGuest(identity: Identity | null | undefined): boolean {
  if (!identity || identity.is_anonymous) return false
  return identity.is_guest && identity.login_provider !== 'qq'
}

/** 真正的账号：不是共享匿名桶，也不是只活在本浏览器里的游客。 */
export function isRealAccount(identity: Identity | null | undefined): boolean {
  if (!identity || identity.is_anonymous) return false
  return !isMintedGuest(identity)
}

/** 合成占位邮箱（qq-{openid}@qq.local / guest-…@guest.local）。
 *  后端正在改成不再下发这类地址，所以这里按"可能是合成串、可能是 null、
 *  也可能整个字段都没有"三种形态都成立来写——只靠其中一种判断都会有一天失效。 */
export function isSyntheticEmail(email: string | null | undefined): boolean {
  if (!email) return false
  return /@(qq|guest)\.local$/i.test(email.trim())
}

/** 可以展示给用户看的邮箱；拿不出真邮箱时返回 null（由调用方决定怎么留白）。 */
export function displayableEmail(identity: Identity | null | undefined): string | null {
  const email = identity?.email
  if (!email) return null
  // 身份形态优先：QQ 号与游客号的 email 在后端本来就是占位串，不管它长什么样。
  if (identity.login_provider === 'qq' || identity.is_guest) return null
  if (isSyntheticEmail(email)) return null
  return email
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
  /**
   * 展示名的 **key，不是文案**：这张表在模块求值时就固定了，存翻译结果的话
   * 切换语言不会重新求值，预设名会一直停在打开页面时的那种语言。
   * 渲染处写 t(preset.nameKey)。
   *
   * 译文在 i18n/locales/{zh,en}/catalog.brand.ts —— 那里放的是**厂商官方英文名**
   * 而不是直译（通义千问 → Qwen、智谱 GLM → Zhipu GLM），见契约 6.11 / 12.2。
   */
  nameKey: PlainMessageKey
  api_base: string
  model: string
}

// 模型名核实于 2026-07-21（各厂商 API 文档/更新日志），见 docs/MAINTENANCE.md「4.3.5 服务商预设保鲜」
// 「服务商预设」一节。这类默认值有时效性——厂商换代快，过一阵子要再核一遍。
export const OPENAI_COMPATIBLE_PRESETS: OpenAICompatiblePreset[] = [
  { id: 'openai', nameKey: 'catalog.brand.openai', api_base: 'https://api.openai.com/v1', model: 'gpt-5.2' },
  { id: 'deepseek', nameKey: 'catalog.brand.deepseek', api_base: 'https://api.deepseek.com', model: 'deepseek-v4-pro' },
  { id: 'kimi', nameKey: 'catalog.brand.kimi', api_base: 'https://api.moonshot.cn/v1', model: 'kimi-k3' },
  { id: 'qwen', nameKey: 'catalog.brand.qwen', api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  { id: 'glm', nameKey: 'catalog.brand.glm', api_base: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-5' },
  { id: 'ollama', nameKey: 'catalog.brand.ollama', api_base: 'http://localhost:11434/v1', model: 'llama3' },
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
  /** 首次匿名发起评审时，后端会铸造一个独立游客身份并把令牌带回来——
   *  不存下来的话，下次请求又落回全站共享的 anonymous 桶，刚发起的这条
   *  评审在用户自己眼里就凭空消失了。已经持有身份（游客或登录用户）时为 null。 */
  guest_token: string | null
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
  adaptive_panel: boolean
  wide_screen?: boolean
  skill_type: string | null
  project_key: string | null
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  error_message: string | null
  created_at: string | null
  completed_at: string | null
  target_title: string | null
  total_cost_usd: number
  input_tokens?: number
  output_tokens?: number
  report: ReviewReport | null
  calibration: unknown
  /** 只读分享状态。null = 未分享；只回给作者本人。
   *  这两个字段是加分享功能时在 v2 端点加了返回、却忘了在这里声明的——
   *  被 test_review_serialization_parity 抓出来，正是那条测试存在的理由。 */
  share_token: string | null
  shared_at: string | null
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
  /** CDK 次数余额：credits 模式下这就是全部额度；plan 模式下是日限用完后的加量。
   *  ⚠️ 不要拿它判断"还能不能发起评审"——刚铸造的游客余额恒为 0，但他还有
   *  trial_credits_remaining 次免费机会。判断一律用 reviews_remaining。 */
  bonus_credits: number
  /** 游客一次性体验额度剩余；非游客账号为 null（"不适用"，不是 0） */
  trial_credits_remaining: number | null
  /** 体验额度初始值，用于显示 "2 / 3"；非游客为 null */
  trial_credits_total: number | null
  /** **唯一**该用来判断"还能不能发起评审"的字段：体验额度 + CDK 余额 + 日限剩余，
   *  由后端与 check_quota 同源算出。null = 不设限（配额整体关闭）。
   *  前端自己重算必然与 402 分岔——这正是它存在的原因。 */
  reviews_remaining: number | null
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
  /** 所属评审的标题/项目名（ledger_service.list_judgments 随行带出）。
   *  追踪卡按 project_key（缺则 review_title）分组展示"哪个项目还欠着回填"。 */
  review_title?: string | null
  project_key?: string | null
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

/** 置信度校准：预测时说的把握 vs 回填后的真实结果。
 *
 * 与 HitRate 的分工：HitRate 回答"说中了几次"，这个回答"说自己有多大把握时
 * 准不准"——一个恒说 90% 却只对一半的面板，hit_rate 看不出问题，校准能。
 *
 * 所有指标在样本为空时是 null 而不是 0：0 分是"预测完美"的意思（Brier 越低越好），
 * 拿它表示"没数据"会把空账本显示成满分。
 */
export interface ConfidenceCalibration {
  persona_id: string | null
  sample_size: number
  /** 已回填真实结果的判断条数（含被排除的） */
  verified_rows: number
  /** 因为没有 confidence 或 verdict 无法映射而被排除的条数 */
  excluded_rows: number
  mean_predicted_confidence: number | null
  /** 真实命中得分均值。hit=1 / partial=0.5 / miss=0 */
  observed_hit_score: number | null
  /** Brier 分数，越低越好（0 = 完美）。null = 无样本 */
  brier_score: number | null
  /** 期望校准误差：各置信度区间内「说的把握」与「真实结果」的加权平均差 */
  expected_calibration_error: number | null
  bins: Array<{
    lower: number
    upper: number
    sample_size: number
    mean_confidence: number | null
    observed_hit_score: number | null
    gap: number | null
  }>
  outcome_mapping: Record<string, number>
  confidence_source: string
  /** 样本不足时为 true —— 同 HitRate，UI 必须如实展示，不能拿几个样本谈校准 */
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

/**
 * v2 进度事件名。**这是后端 WS_EVENTS 元组的镜像，改一边就要改另一边。**
 *
 * 这里曾经列着 13 个名字，其中 6 个后端从未推送过：persona_started /
 * persona_failed / cross_exam_started / cross_exam_completed /
 * aggregation_started / aggregation_completed。它们不是"暂时没用上"——
 * 是**没有任何后端代码路径会发出它们**，于是任何按这些名字写的分支都是
 * 看起来活着的死代码，而读代码的人分不清哪几个是真契约。已全部删除
 * （删前确认过：没有任何组件 switch 到它们；ReviewProgressPage 里同名的
 * 'persona_started' 等 case 属于 v1 的 WSMessage，与这个联合无关）。
 *
 * 'review.cancelled' 保留：后端正在补这条广播，且 ws.ts 的 TERMINAL 已经
 * 按终态处理它，行为是对的。
 */
export type WsEventName =
  | 'review.started'
  | 'review.progress'
  | 'review.persona_completed'
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
  /** 所属项目，null = 未分组。真外键，删项目会让它回到 null（不删对话）。 */
  project_id: string | null
  created_at: string | null
  /** 列表按它倒序。按 created_at 排会让老对话里的新消息沉底。 */
  updated_at: string | null
}

// ---------------- 项目：对话的分组容器 ----------------
// 与 Review.project_key（旧的自由文本标签，供独立的评审历史页分组）是两套
// 并存的系统，不合并——见后端 models.Project 的类文档。

export interface Project {
  id: string
  name: string
  /** 现查的真实计数，不是创建时缓存下来的快照 */
  conversation_count: number
  created_at: string | null
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
