import { Lightbulb, Settings, BookOpen, Target, Coins, Store, Rocket, MessageCircle, Globe, Users, FolderOpen, TrendingUp, Smartphone, Volume2, Film, LayoutDashboard, MessageSquareText, Tag, Compass, Briefcase } from 'lucide-react'

export type Severity = 'critical' | 'high' | 'medium' | 'low'
export type PrimaryStance = 'advocate' | 'neutral' | 'skeptic' | 'blocker'
export type RiskLevel = 'green' | 'yellow' | 'orange' | 'red'
export type SkillType = 'synthetic_playtest' | 'audience_panel' | 'red_team_audience' | 'persona_generate'

export interface EvaluationResult {
  dimension: string
  score: number
  passed: boolean
  details: string
}

export interface EvaluationScorecard {
  overall_score: number
  passed: boolean
  results: EvaluationResult[]
  critical_failures: string[]
}

/** 伦理违规的严重度。后端 ethics_service 只从 RISK_KEYWORDS 的键里取值
 * （high / medium / low，一个都没命中时兜底成 medium），不会出现站内 Severity
 * 里的 critical——所以单独定义一个类型，别跟 Severity 混用。 */
export type EthicsSeverity = 'high' | 'medium' | 'low'

/** 刻板印象风险档位。后端 ethics_service.evaluate_persona_output 是按
 * high_count / medium_count 直接赋 'high' / 'medium' / 'low' 三档字符串的，
 * 它从来不是 0–1 的连续量：以前前端当小数乘 100 显示，结果每张卡片都是
 * NaN%，颜色判断 'low' < 0.3 恒为 false，于是所有人格永远被标成高风险。 */
export type StereotypeRisk = 'high' | 'medium' | 'low'

/** 一条伦理违规。字段与后端 ethics_service 里 append 的 dict 一一对应：
 * severity 是严重度，rule 是命中的规则 id，detail 是人类可读描述。 */
export interface EthicsViolation {
  severity: EthicsSeverity
  rule: string
  detail: string
}

/** violations 的数组元素有两种形态：新数据是上面的 EthicsViolation 对象；
 * 早期版本把 check_stereotypes() 返回的 "[rule_id] 描述" 字符串原样存进了
 * violations_json，库里还留着这种老行。类型上如实承认两种形态，渲染侧靠
 * 类型守卫分流——之前类型写成 string[] 却收到 dict，才导致对象被直接塞进
 * JSX、React 抛 "Objects are not valid as a React child" 整页白屏。 */
export type EthicsViolationEntry = EthicsViolation | string

export interface EthicsReport {
  persona_id: string
  passed: boolean
  score: number
  violations: EthicsViolationEntry[]
  stereotype_risk: StereotypeRisk
}

/** 展示用的违规视图：老数据补不出 rule 时为 null，UI 就不画规则徽标。 */
export interface EthicsViolationView {
  severity: EthicsSeverity
  rule: string | null
  detail: string
}

function isEthicsSeverity(value: unknown): value is EthicsSeverity {
  return value === 'high' || value === 'medium' || value === 'low'
}

/** 类型守卫：三个字段都合规才认成新格式的违规对象。
 * 这里不用 as EthicsViolation，因为数据是后端 JSON——断言只会把
 * 「把对象当字符串渲染」的崩溃从编译期推到运行期。 */
export function isEthicsViolation(entry: unknown): entry is EthicsViolation {
  return (
    typeof entry === 'object' && entry !== null &&
    'severity' in entry && isEthicsSeverity(entry.severity) &&
    'rule' in entry && typeof entry.rule === 'string' &&
    'detail' in entry && typeof entry.detail === 'string'
  )
}

/** 老数据形态是 "[gender_assumption] 基于性别的刻板假设"。 */
const LEGACY_VIOLATION_RE = /^\[([^\]]+)\]\s*(.*)$/

/** 把任意一条 violations 元素收敛成可渲染的视图。入参用 unknown 而不是
 * EthicsViolationEntry，是因为这值最终来自网络 JSON，运行时可能连这两种
 * 形态都不是；宁可显示一条「读不懂的记录」，也不要整页崩掉。 */
export function toEthicsViolationView(entry: unknown): EthicsViolationView {
  if (isEthicsViolation(entry)) {
    return { severity: entry.severity, rule: entry.rule, detail: entry.detail }
  }
  if (typeof entry === 'string') {
    // 按后端同样的拆法把 rule 前缀拆出来，老报告也能显示规则 id
    const matched = LEGACY_VIOLATION_RE.exec(entry)
    if (matched) {
      return { severity: 'medium', rule: matched[1], detail: matched[2] || entry }
    }
    return { severity: 'medium', rule: null, detail: entry }
  }
  return { severity: 'medium', rule: null, detail: '（这条违规记录格式无法识别）' }
}

/** 收敛 stereotype_risk：认不出来（老数据里的数字、空串、拼错的枚举）就返回
 * null，让 UI 显示「未知」。宁可承认读不懂，也不要像以前那样一律标红。 */
export function toStereotypeRisk(value: unknown): StereotypeRisk | null {
  return isEthicsSeverity(value) ? value : null
}

/** 展示用的伦理报告：两个易漂移的字段都已经收敛过，UI 拿到就能直接渲染。 */
export interface EthicsReportView {
  persona_id: string
  passed: boolean
  score: number
  violations: EthicsViolationView[]
  stereotype_risk: StereotypeRisk | null
}

/** 在 API 边界做一次性收敛，而不是在 JSX 里逐个判断：这样页面里既不会重复
 * 调守卫，也不可能有人不小心又把原始 dict 直接渲染出去。violations 这里再
 * 兜一层 Array.isArray，是防老后端/老缓存整个字段都没给。 */
export function toEthicsReportView(report: EthicsReport): EthicsReportView {
  return {
    persona_id: report.persona_id,
    passed: report.passed,
    score: report.score,
    violations: Array.isArray(report.violations) ? report.violations.map(toEthicsViolationView) : [],
    stereotype_risk: toStereotypeRisk(report.stereotype_risk),
  }
}

const STEREOTYPE_RISK_LABELS: Record<StereotypeRisk, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
}

/** 三档配色：低=品牌金（正常），中=severity-medium，高=severity-critical。
 * 全部走语义 token，配色从暖金换古铜金时不需要动这里。 */
const STEREOTYPE_RISK_BADGE_CLASSES: Record<StereotypeRisk, string> = {
  low: 'bg-brand-primary/10 text-brand-primary',
  medium: 'bg-severity-medium/10 text-severity-medium',
  high: 'bg-severity-critical/10 text-severity-critical',
}

export function stereotypeRiskLabel(risk: StereotypeRisk | null): string {
  return risk === null ? '未知' : STEREOTYPE_RISK_LABELS[risk]
}

export function stereotypeRiskBadgeClass(risk: StereotypeRisk | null): string {
  return risk === null ? 'bg-bg-secondary text-text-muted' : STEREOTYPE_RISK_BADGE_CLASSES[risk]
}

/** severity 徽标文案与配色。三档整体上移一档（high→critical、medium→high、
 * low→medium）：违规项本身就是坏消息，最高一档该用站内最红的 critical；
 * 而 severity-low 是青色，在站内读起来像「没问题」，用在违规上会误导。 */
export const ETHICS_SEVERITY_LABELS: Record<EthicsSeverity, string> = {
  high: '高危',
  medium: '中危',
  low: '低危',
}

export const ETHICS_SEVERITY_BADGE_CLASSES: Record<EthicsSeverity, string> = {
  high: 'bg-severity-critical/10 text-severity-critical',
  medium: 'bg-severity-high/10 text-severity-high',
  low: 'bg-severity-medium/10 text-severity-medium',
}

export interface SkillDetail {
  name: string
  description_zh: string
  task_types: string[]
  persona_count: number
  use_cases: string[]
}

export interface BehaviorAxis {
  axis: string
  value: number
}

export interface Persona {
  id: string
  name: string
  archetype: string
  identity_summary: string
  behavior_profile: Record<string, number>
  gaming_profile?: Record<string, unknown>
  pack?: string
  decisionRules?: string[]
  triggers?: string[]
}

export interface PersonaPack {
  panel_id: string
  name: string
  description: string
  persona_count: number
  category: string
}

export type ReviewMode = 'quick' | 'standard' | 'full'

export interface ReviewModeConfig {
  mode: ReviewMode
  persona_count_range: [number, number]
  cross_examination: boolean
  calibration: boolean
  description: string
}

// ---------- 交叉质询（report_json.cross_examination） ----------
//
// 字段契约以 src/runner/cross_exam.py::run_cross_exam_protocol 的返回体为准。
// 这里全部做运行时收敛而不是 `as CrossExamView`：这份数据来自数据库里的
// report_json，库里同时存在三代形状——
//   1. 当前形状：带 mode / threshold / suppressed_changes 的完整 dict；
//   2. 老引擎形状：dict，但只有 mode/is_live_debate/limitation/disputes/
//      vote_changes/confidence_changes/rounds，缺 threshold 等新字段；
//   3. 老 v1 后端形状：直接把 parse_cross_exam_output 的**原始数组**存了进去，
//      里面是模型自由输出的 JSON，没有任何可依赖的字段。
// 断言只会把「读不出字段」从编译期推到运行期——本仓库刚因为「前端类型撒谎」
// 出过整页白屏和 NaN%，这一次从类型开始就如实承认多形态。

/** 三档模式是三件不同的事，用户有权知道自己这份报告是哪一种：
 *  derived_summary     —— 没跑反驳轮，内容由各人格原始输出派生；
 *  moderated_rebuttal  —— 一次仲裁式反驳轮（模型统一处理全部争议点）；
 *  multi_agent_rebuttal—— 每位涉事人格各自被重新调用一次。 */
export type CrossExamMode = 'derived_summary' | 'moderated_rebuttal' | 'multi_agent_rebuttal'

/** 单个争议点的反驳完成度。partial = 只有一方产出了反驳，不能显示成"已完成"。 */
export type RebuttalStatus = 'ok' | 'partial' | 'failed' | 'skipped'

const CROSS_EXAM_MODES: CrossExamMode[] = ['derived_summary', 'moderated_rebuttal', 'multi_agent_rebuttal']
const REBUTTAL_STATUSES: RebuttalStatus[] = ['ok', 'partial', 'failed', 'skipped']

/** 一条论据。注意 persona_id 放的是**展示名**（引擎里的历史口径，为了兼容
 *  report-template.html），真 id 在 persona_key —— 两个字段别弄反。 */
export interface CrossExamArgument {
  argument_id: string
  point: string
  /** 展示名（历史口径） */
  persona_id: string
  /** 真 persona id */
  persona_key: string
  severity: string
  /** 这一方针对**对方**论据写出的反驳；没跑反驳轮时为空串 */
  rebuttal: string
}

export interface CrossExamDispute {
  point_id: string
  topic: string
  /** A 系列：认为问题更严重的一方 */
  pro_args: CrossExamArgument[]
  /** B 系列：认为问题更轻的一方 */
  con_args: CrossExamArgument[]
  rebuttal_status: RebuttalStatus
  rebuttal_error: string
}

/** 改票记录。这里的 persona_id 是**真 id**，展示要用 persona_name（引擎在
 *  vote_changes 与 confidence_changes 两处的 persona_id 语义不同，别复用读法）。
 *  suppressed_reason 只出现在 suppressed_changes 里。 */
export interface CrossExamVoteChange {
  point_id: string
  topic: string
  argument_id: string
  persona_id: string
  persona_name: string
  from_stance: string
  to_stance: string
  /** 0–1 小数；读不出来时为 null，UI 显示 "—" 而不是 NaN */
  confidence_before: number | null
  confidence_after: number | null
  delta: number | null
  threshold: number | null
  reason: string
  suppressed_reason: string
}

/** 逐人格的置信度变化。before/after/delta 是**百分点整数**（引擎已乘 100 取整），
 *  confidence_* 才是 0–1 小数——别把百分点再乘一次 100。 */
export interface CrossExamConfidenceChange {
  /** 展示名（历史口径） */
  persona_id: string
  /** 真 persona id */
  persona_key: string
  before: number | null
  after: number | null
  delta: number | null
  confidence_before: number | null
  confidence_after: number | null
}

export interface CrossExamFailure {
  stage: string
  error: string
  point_id: string
  argument_id: string
}

export interface CrossExamUsage {
  calls: number
  input_tokens: number
  output_tokens: number
  /** false 表示模型只回了文本、拿不到 token 数，成本统计可能偏低 */
  token_counts_available: boolean
}

export interface CrossExamView {
  /** 收敛后的三档模式；认不出来时为 null（UI 显示"未知模式"而不是假装派生摘要） */
  mode: CrossExamMode | null
  /** 引擎给的原始 mode 字符串，认不出来时原样展示，便于排查 */
  mode_raw: string
  /**
   * 真的发生过反驳 LLM 调用吗。
   * 取 mode 与 is_live_debate 的**交集**：协议里两者恒等（is_live_debate 严格由
   * mode 推出），一旦库里的数据两者不一致，说明这行是老数据或被改坏了——
   * 此时按更保守的那个读。宁可少声称"跑了辩论"，不可多声称。
   */
  is_live_debate: boolean
  /** 调用方请求的模式；与 mode 不同就是发生了回落 */
  requested_mode: CrossExamMode | null
  requested_mode_raw: string
  /** 引擎生成的局限说明，原样展示，不做改写 */
  limitation: string
  threshold: number | null
  threshold_source: string
  allow_stance_update: boolean
  /** 实际执行的反驳轮数（derived 时为 0） */
  rounds_run: number
  disputes: CrossExamDispute[]
  vote_changes: CrossExamVoteChange[]
  suppressed_changes: CrossExamVoteChange[]
  confidence_changes: CrossExamConfidenceChange[]
  failures: CrossExamFailure[]
  usage: CrossExamUsage | null
  /** true = 老 v1 后端存下的原始数组形状，字段读不出来，只能如实说明 */
  is_legacy_array: boolean
  /** 老数组形状下的元素条数，用于告诉用户"有记录但格式过旧" */
  legacy_entry_count: number
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function asText(value: unknown): string {
  if (typeof value === 'string') return value.trim()
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return ''
}

/** 数字收敛：非有限数（null / undefined / "" / NaN / 对象）一律返回 null。
 *  返回 0 会是撒谎——"delta 为 0"和"读不出 delta"在报告里含义完全不同。 */
function asFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function asNonNegativeInt(value: unknown): number {
  const num = asFiniteNumber(value)
  return num === null || num < 0 ? 0 : Math.round(num)
}

function asCrossExamMode(value: unknown): CrossExamMode | null {
  return CROSS_EXAM_MODES.includes(value as CrossExamMode) ? (value as CrossExamMode) : null
}

function toCrossExamArgument(raw: unknown): CrossExamArgument {
  const r = isRecord(raw) ? raw : {}
  return {
    argument_id: asText(r.argument_id),
    point: asText(r.point),
    persona_id: asText(r.persona_id),
    persona_key: asText(r.persona_key),
    severity: asText(r.severity),
    rebuttal: asText(r.rebuttal),
  }
}

function toCrossExamDispute(raw: unknown): CrossExamDispute {
  const r = isRecord(raw) ? raw : {}
  const status = REBUTTAL_STATUSES.includes(r.rebuttal_status as RebuttalStatus)
    ? (r.rebuttal_status as RebuttalStatus)
    // 老数据没有这个字段：不能默认成 'ok'（那就是把"未知"说成"已完成"）
    : 'skipped'
  return {
    point_id: asText(r.point_id),
    topic: asText(r.topic),
    pro_args: (Array.isArray(r.pro_args) ? r.pro_args : []).map(toCrossExamArgument),
    con_args: (Array.isArray(r.con_args) ? r.con_args : []).map(toCrossExamArgument),
    rebuttal_status: status,
    rebuttal_error: asText(r.rebuttal_error),
  }
}

function toCrossExamVoteChange(raw: unknown): CrossExamVoteChange {
  const r = isRecord(raw) ? raw : {}
  return {
    point_id: asText(r.point_id),
    topic: asText(r.topic),
    argument_id: asText(r.argument_id),
    persona_id: asText(r.persona_id),
    persona_name: asText(r.persona_name),
    // 老引擎只写了 before/after 两个别名，新引擎两套都写；读不到新名就退回别名
    from_stance: asText(r.from_stance) || asText(r.before),
    to_stance: asText(r.to_stance) || asText(r.after),
    confidence_before: asFiniteNumber(r.confidence_before),
    confidence_after: asFiniteNumber(r.confidence_after),
    delta: asFiniteNumber(r.delta),
    threshold: asFiniteNumber(r.threshold),
    reason: asText(r.reason),
    suppressed_reason: asText(r.suppressed_reason),
  }
}

function toCrossExamConfidenceChange(raw: unknown): CrossExamConfidenceChange {
  const r = isRecord(raw) ? raw : {}
  return {
    persona_id: asText(r.persona_id),
    persona_key: asText(r.persona_key),
    before: asFiniteNumber(r.before),
    after: asFiniteNumber(r.after),
    delta: asFiniteNumber(r.delta),
    confidence_before: asFiniteNumber(r.confidence_before),
    confidence_after: asFiniteNumber(r.confidence_after),
  }
}

function toCrossExamFailure(raw: unknown): CrossExamFailure {
  const r = isRecord(raw) ? raw : {}
  return {
    stage: asText(r.stage),
    error: asText(r.error) || (typeof raw === 'string' ? raw.trim() : ''),
    point_id: asText(r.point_id),
    argument_id: asText(r.argument_id),
  }
}

/**
 * 把 report_json.cross_examination 收敛成可直接渲染的视图。
 *
 * 返回 null 只代表"这份报告里没有交叉质询区块"（quick 档不跑、匿名体验版被
 * report_gating 裁成 null、老报告根本没这个键）——此时页面整节不渲染。
 * 而"跑了但失败了"是有区块的，会带 failures / limitation，必须显示出来：
 * 这两种情况在页面上长得一样，就等于把失败伪装成了没做。
 */
export function toCrossExamView(raw: unknown): CrossExamView | null {
  if (raw === null || raw === undefined) return null

  const empty: CrossExamView = {
    mode: null,
    mode_raw: '',
    is_live_debate: false,
    requested_mode: null,
    requested_mode_raw: '',
    limitation: '',
    threshold: null,
    threshold_source: '',
    allow_stance_update: true,
    rounds_run: 0,
    disputes: [],
    vote_changes: [],
    suppressed_changes: [],
    confidence_changes: [],
    failures: [],
    usage: null,
    is_legacy_array: false,
    legacy_entry_count: 0,
  }

  // 老 v1 后端把模型原始输出的数组存进了这个字段。里面是自由 JSON，硬解只会
  // 把猜测当事实——如实标成"格式过旧"，让 UI 说明"这份报告读不出反驳明细"。
  if (Array.isArray(raw)) {
    return { ...empty, is_legacy_array: true, legacy_entry_count: raw.length }
  }
  if (!isRecord(raw)) return null

  const mode = asCrossExamMode(raw.mode)
  const liveByMode = mode === 'moderated_rebuttal' || mode === 'multi_agent_rebuttal'
  const allowUpdate = raw.allow_stance_update

  return {
    ...empty,
    mode,
    mode_raw: asText(raw.mode),
    // 见 CrossExamView.is_live_debate 的注释：两个字段必须同时为真
    is_live_debate: liveByMode && raw.is_live_debate === true,
    requested_mode: asCrossExamMode(raw.requested_mode),
    requested_mode_raw: asText(raw.requested_mode),
    limitation: asText(raw.limitation),
    threshold: asFiniteNumber(raw.threshold),
    threshold_source: asText(raw.threshold_source),
    allow_stance_update: typeof allowUpdate === 'boolean' ? allowUpdate : true,
    rounds_run: Array.isArray(raw.rounds) ? raw.rounds.length : 0,
    disputes: (Array.isArray(raw.disputes) ? raw.disputes : []).map(toCrossExamDispute),
    vote_changes: (Array.isArray(raw.vote_changes) ? raw.vote_changes : []).map(toCrossExamVoteChange),
    suppressed_changes: (Array.isArray(raw.suppressed_changes) ? raw.suppressed_changes : []).map(toCrossExamVoteChange),
    confidence_changes: (Array.isArray(raw.confidence_changes) ? raw.confidence_changes : []).map(toCrossExamConfidenceChange),
    failures: (Array.isArray(raw.failures) ? raw.failures : []).map(toCrossExamFailure),
    usage: isRecord(raw.usage)
      ? {
          calls: asNonNegativeInt(raw.usage.calls),
          input_tokens: asNonNegativeInt(raw.usage.input_tokens),
          output_tokens: asNonNegativeInt(raw.usage.output_tokens),
          // 缺这个键的老数据按 false 处理：没证据说明 token 数可信时不该声称可信
          token_counts_available: raw.usage.token_counts_available === true,
        }
      : null,
  }
}

/** 三档模式的展示文案。措辞与 cross_exam.py 的 limitation 口径一致，
 *  尤其 moderated 档必须写明"不是每个人格各自独立重新发言"——含糊就是撒谎。 */
export const CROSS_EXAM_MODE_LABELS: Record<CrossExamMode, string> = {
  derived_summary: '派生摘要（未进行反驳轮）',
  moderated_rebuttal: '仲裁式反驳（1 轮）',
  multi_agent_rebuttal: '多智能体反驳',
}

export const CROSS_EXAM_MODE_DESCRIPTIONS: Record<CrossExamMode, string> = {
  derived_summary:
    '本节没有进行反驳轮：内容全部由各人格独立评审时的原始输出派生而来，人格之间没有相互反驳，也没有人因此改票。',
  moderated_rebuttal:
    '本次执行了一次仲裁式反驳轮：模型拿到双方已记录的论据后统一给出反驳与更新后的立场。这不是每个人格各自独立重新发言。',
  multi_agent_rebuttal:
    '本次执行了多智能体反驳：每位涉事人格都带着对手的论据被重新调用一次，各自产出反驳与最终立场。',
}

/** 反驳完成度的展示文案。'ok' 之外都必须让人一眼看出"这条没跑完"。 */
export const REBUTTAL_STATUS_LABELS: Record<RebuttalStatus, string> = {
  ok: '双方均已反驳',
  partial: '仅单方反驳',
  failed: '反驳未完成',
  skipped: '未进行反驳',
}

export const REBUTTAL_STATUS_CLASSES: Record<RebuttalStatus, string> = {
  ok: 'bg-brand-primary/10 text-brand-primary',
  partial: 'bg-severity-medium/10 text-severity-medium',
  failed: 'bg-severity-critical/10 text-severity-critical',
  skipped: 'bg-bg-secondary text-text-muted',
}

export interface TaskTypeDetail {
  task_type: string
  name_zh: string
  description: string
  stance_enum: string[]
  score_dimensions: string[]
  base_dimensions: string[]
}

export interface ReviewResultData {
  session_id: string
  report_json: unknown
  report_md: string | null
  report_html: string | null
}

export interface TaskType {
  id: string
  name: string
  description: string
  icon: string
  category: string
  IconComponent: React.ComponentType<{ className?: string; strokeWidth?: number }>
  stance_enum?: string[]
  score_dimensions?: string[]
}

export interface PersonaOutput {
  id: string
  review_id: string
  persona_id: string
  persona_name: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  output_json: unknown
  validation_result: unknown
  cost_usd: number
  started_at: string | null
  completed_at: string | null
}

export interface Issue {
  id: string
  title: string
  severity: Severity
  description: string
  evidence: string[]
  affectedPersonas: string[]
}

export interface PersonaPerspective {
  personaId: string
  personaName: string
  archetype: string
  stance: PrimaryStance
  confidence: number
  quote: string
  keyEvidence: string[]
}

export interface CalibrationMetrics {
  consistency: number
  coverage: number
  hallucination: number
}

export interface Report {
  reviewId: string
  riskLevel: RiskLevel
  riskSummary: string
  stanceDistribution: { stance: PrimaryStance; count: number }[]
  priorityIssues: Issue[]
  personaPerspectives: PersonaPerspective[]
  informationGaps: string[]
  calibration: CalibrationMetrics
}

export interface Review {
  id: string
  task_type: string
  target_title: string
  artifact_bundle: Record<string, unknown>
  persona_pack?: string
  selected_personas?: string[]
  adaptive_panel: boolean
  mode: ReviewMode
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  completed_at: string | null
  total_cost_usd: number
  report_json: unknown
  report_markdown: string | null
  calibration: unknown
  persona_outputs: PersonaOutput[]
  skill_type?: SkillType
  /** 长期评审项目分组键——同名评审在历史侧栏聚合成一组 */
  project_key?: string
  evaluation_scorecard?: EvaluationScorecard
  ethics_reports?: EthicsReport[]
  /** 只读分享状态。null/缺省 = 未分享。只会回给作者本人（后端所有吐
   *  ReviewResponse 的端点都先过 _check_review_owner）。 */
  share_token?: string | null
  shared_at?: string | null
  /** 功能完整性审查 P1：后端 ReviewResponse 一直有这两个字段，前端类型
   *  之前没声明，走 v1 客户端（api.ts::fetchReview）的调用方读不到——具体
   *  后果见 schemas/__init__.py 里 error_message 字段上的注释："引擎写了
   *  半份报告又失败时 report_json 非空，旧兜底分支不触发，此时唯一能看到
   *  失败原因的地方就是这个字段"，以及 skill_degraded 上的注释："走 v1
   *  的用户会以为红队/高级技能正常跑了，静默降级是本仓库要根除的形状"。 */
  error_message?: string | null
  skill_degraded?: string | null
  input_tokens?: number
  output_tokens?: number
}

/** GET /api/reviews 的列表项——后端返回的是瘦身字段（见后端
 * ReviewListItemResponse）：不含 artifact_bundle / report_json /
 * persona_outputs，因为侧栏只画一行标题，不该为此把每条评审的 base64
 * 截图和完整报告全量拖下来。需要完整内容时按 id 走 fetchReview()。 */
export interface ReviewListItem {
  id: string
  task_type: string
  target_title: string
  project_key?: string
  mode: ReviewMode
  status: 'pending' | 'running' | 'completed' | 'failed'
  created_at: string
  completed_at: string | null
  total_cost_usd: number
  input_tokens?: number
  output_tokens?: number
}

export interface Example {
  id: string
  title: string
  type: string
  description: string
  artifact_bundle: {
    title: string
    type: string
    description: string
    materials: { type: string; description: string }[]
    [key: string]: unknown
  }
}

export interface Preset {
  task_type: string
  default_personas: string[]
  optional_personas: string[]
}

export interface WSMessage {
  type: string
  persona_id?: string
  persona_name?: string
  validation_passed?: boolean
  cost_usd?: number
  error?: string
}

export function behaviorProfileToAxes(profile: Record<string, number>): BehaviorAxis[] {
  return Object.entries(profile).map(([axis, value]) => ({ axis, value }))
}

export const PACK_ICONS: Record<string, string> = {
  'game-core': '🎮',
  'competitive-esport': '🏆',
  'family-casual': '👨‍👩‍👧‍👦',
  'mobile-f2p': '📱',
  'accessibility': '♿',
  'vr-immersive': '🥽',
  'educational-serious': '📚',
  'indie-creative': '🎨',
}

export const BEHAVIOR_AXES = [
  '攻击性', '探索性', '社交性', '创造性',
  '竞争性', '合作性', '风险偏好', '耐心',
  '完美主义', '沉浸感', '策略性', '表现欲',
]

export interface TaskMaterialField {
  key: string
  label: string
  placeholder: string
  required: boolean
}

export const TASK_MATERIALS: Record<string, TaskMaterialField[]> = {
  concept_review: [
    { key: '一句话pitch', label: '一句话介绍', placeholder: '用一句话描述你的游戏核心概念...', required: true },
    { key: '核心循环说明', label: '核心玩法循环', placeholder: '描述游戏的核心循环：探索→战斗→...', required: true },
    { key: '竞品对比', label: '竞品参考', placeholder: '列出参考竞品，如：Dead Cells（战斗节奏）、Hollow Knight（探索深度）', required: false },
    { key: '目标受众', label: '目标受众', placeholder: '描述目标玩家画像...', required: false },
    { key: '定价与平台', label: '定价与平台', placeholder: '如：抢先体验 $14.99，PC Steam首发', required: false },
    { key: '截图', label: '截图/视觉描述', placeholder: '描述游戏视觉风格，或上传截图...', required: false },
    { key: '系统说明', label: '核心系统说明', placeholder: '描述3-5个核心系统...', required: false },
  ],
  demo_first_play: [
    { key: '游戏名称', label: '游戏名称', placeholder: '输入游戏名称', required: true },
    { key: '核心循环说明', label: '核心玩法', placeholder: '描述试玩版包含的核心玩法...', required: true },
    { key: '截图', label: '截图/视觉描述', placeholder: '描述游戏画面风格...', required: false },
    { key: '实机视频', label: '实机视频描述', placeholder: '描述视频内容或粘贴视频链接...', required: false },
    { key: '竞品对比', label: '竞品参考', placeholder: '列出参考竞品...', required: false },
    { key: '评价摘要', label: '已有评价', placeholder: '粘贴已有的玩家评价（如有）...', required: false },
  ],
  steam_page_review: [
    { key: '游戏名称', label: '游戏名称', placeholder: '输入游戏名称', required: true },
    { key: '截图', label: '胶囊图/截图描述', placeholder: '描述Steam胶囊图和截图内容...', required: true },
    { key: '核心循环说明', label: '游戏简介', placeholder: '粘贴Steam商店页的简短描述...', required: true },
    { key: 'tags', label: '标签', placeholder: '如：roguelite, metroidvania, pixel art', required: false },
    { key: '价格', label: '价格', placeholder: '如：$19.99', required: false },
    { key: '评价摘要', label: '用户评价', placeholder: '粘贴已有的用户评价摘要...', required: false },
    { key: 'demo', label: 'Demo信息', placeholder: '是否有Demo，包含什么内容...', required: false },
  ],
  kickstarter_review: [
    { key: '项目名称', label: '项目名称', placeholder: '输入众筹项目名称', required: true },
    { key: '一句话pitch', label: '一句话介绍', placeholder: '项目的核心卖点...', required: true },
    { key: '核心循环说明', label: '项目描述', placeholder: '描述项目的核心内容和特色...', required: true },
    { key: '定价与平台', label: '回报档位', placeholder: '列出各档位的价格和内容...', required: true },
    { key: '截图', label: '视觉素材描述', placeholder: '描述众筹页的图片和视频内容...', required: false },
    { key: '目标受众', label: '目标支持者', placeholder: '描述目标支持者画像...', required: false },
  ],
  discord_community_review: [
    { key: '社区名称', label: '社区名称', placeholder: '如：Echoes of the Void 官方Discord', required: true },
    { key: '核心循环说明', label: '社区描述', placeholder: '描述社区的主题和规模...', required: true },
    { key: '评价摘要', label: '近期帖子摘要', placeholder: '粘贴3-5条近期代表性帖子...', required: true },
    { key: '系统说明', label: '频道结构', placeholder: '列出主要频道和规则...', required: false },
    { key: '竞品对比', label: '竞品社区对比', placeholder: '对比其他类似游戏的社区...', required: false },
  ],
  devlog_review: [
    { key: '游戏名称', label: '游戏名称', placeholder: '输入游戏名称', required: true },
    { key: '核心循环说明', label: '开发日志内容', placeholder: '粘贴开发日志全文或摘要...', required: true },
    { key: '评价摘要', label: '社区反馈', placeholder: '粘贴社区对日志的反馈...', required: false },
    { key: '截图', label: '配图描述', placeholder: '描述日志中的截图/GIF内容...', required: false },
  ],
  monetization_review: [
    { key: '游戏名称', label: '游戏名称', placeholder: '输入游戏名称', required: true },
    { key: '定价与平台', label: '付费方案', placeholder: '描述付费模型：买断/免费+内购/订阅...', required: true },
    { key: '核心循环说明', label: '核心玩法', placeholder: '描述游戏核心循环...', required: true },
    { key: '竞品对比', label: '竞品定价', placeholder: '列出竞品的定价策略...', required: false },
    { key: '评价摘要', label: '玩家反馈', placeholder: '粘贴玩家对定价的反馈...', required: false },
  ],
  update_announcement_review: [
    { key: '游戏名称', label: '游戏名称', placeholder: '输入游戏名称', required: true },
    { key: '核心循环说明', label: '更新内容', placeholder: '粘贴更新公告全文...', required: true },
    { key: '评价摘要', label: '玩家反馈', placeholder: '粘贴玩家对更新的反馈...', required: false },
    { key: '截图', label: '更新截图描述', placeholder: '描述更新中的新内容截图...', required: false },
  ],
  localization_review: [
    { key: '游戏名称', label: '游戏名称', placeholder: '输入游戏名称', required: true },
    { key: '核心循环说明', label: '原文内容', placeholder: '粘贴需要评审的原文文本...', required: true },
    { key: '系统说明', label: '翻译内容', placeholder: '粘贴翻译后的文本...', required: true },
    { key: '竞品对比', label: '文化参考', placeholder: '描述目标文化的特殊考量...', required: false },
  ],
  looking_for_party_post: [
    { key: '游戏名称', label: '游戏名称', placeholder: '输入游戏名称', required: true },
    { key: '核心循环说明', label: '帖子内容', placeholder: '粘贴组队帖全文...', required: true },
    { key: '目标受众', label: '目标玩家', placeholder: '描述你想吸引什么样的玩家...', required: false },
  ],
  // 下面 4 个「通用产品」任务类型此前在本表里没有条目。CreateReviewPage 取字段时
  // 落到 `?? []`，第 2 步「上传材料」会渲染成一个输入框都没有的空页；更糟的是
  // requiredFields 为空使 canNext() 只校验标题非空，用户只填一句标题就能一路启动评审，
  // 拿回一份基于一句话生成的报告却不知道自己漏了材料。所以这里必须有条目，
  // 而不是靠页面兜底——页面兜底只能给一个笼统的「材料正文」，问不出这几类任务真正需要的东西。
  product_feedback_review: [
    { key: '产品名称', label: '产品名称', placeholder: '输入产品或功能名称', required: true },
    { key: '核心循环说明', label: '产品做什么', placeholder: '描述产品解决什么问题、用户怎么用...', required: true },
    { key: '评价摘要', label: '已有用户反馈', placeholder: '粘贴 3-5 条真实用户反馈、工单或评论...', required: true },
    { key: '目标受众', label: '目标用户', placeholder: '描述目标用户画像与使用场景...', required: false },
    { key: '竞品对比', label: '竞品参考', placeholder: '列出用户可能拿来对比的竞品...', required: false },
    { key: '截图', label: '界面截图描述', placeholder: '描述关键界面，或上传截图...', required: false },
  ],
  pricing_page_review: [
    { key: '产品名称', label: '产品名称', placeholder: '输入产品名称', required: true },
    { key: '定价与平台', label: '定价方案', placeholder: '逐档列出：档位名称 / 价格 / 包含什么 / 限制是什么...', required: true },
    { key: '核心循环说明', label: '定价页文案', placeholder: '粘贴定价页上的标题、卖点与说明文字...', required: true },
    { key: '目标受众', label: '目标付费人群', placeholder: '你希望谁来买、他们的预算区间...', required: false },
    { key: '竞品对比', label: '竞品定价', placeholder: '列出竞品的档位与价格...', required: false },
    { key: '截图', label: '页面截图描述', placeholder: '描述定价页的版式与视觉...', required: false },
  ],
  onboarding_review: [
    { key: '产品名称', label: '产品名称', placeholder: '输入产品名称', required: true },
    { key: '核心循环说明', label: '引导流程步骤', placeholder: '按顺序列出新用户从注册到第一次拿到价值的每一步...', required: true },
    { key: '目标受众', label: '新用户是谁', placeholder: '描述新用户的背景、动机与已有认知...', required: true },
    { key: '系统说明', label: '首次价值时刻', placeholder: '用户在哪一步第一次觉得「这东西有用」...', required: false },
    { key: '评价摘要', label: '流失反馈', placeholder: '粘贴新用户流失时的反馈或漏斗观察...', required: false },
    { key: '截图', label: '引导界面描述', placeholder: '描述引导页面/提示的内容与顺序...', required: false },
  ],
  pitch_review: [
    { key: '项目名称', label: '项目名称', placeholder: '输入项目或公司名称', required: true },
    { key: '一句话pitch', label: '一句话介绍', placeholder: '一句话说清你做什么、给谁、解决什么问题...', required: true },
    { key: '核心循环说明', label: 'BP / 路演材料正文', placeholder: '粘贴 BP、路演稿或申报表的正文...', required: true },
    { key: '目标受众', label: '目标市场与客户', placeholder: '描述目标市场规模判断依据与典型客户...', required: true },
    { key: '系统说明', label: '团队与进展', placeholder: '团队背景、当前进展、已有数据或验证...', required: false },
    { key: '定价与平台', label: '商业模式与融资需求', placeholder: '怎么收钱、单位经济、本轮融多少用在哪...', required: false },
    { key: '竞品对比', label: '竞争格局', placeholder: '列出竞争对手与你的差异...', required: false },
  ],
}

export const REVIEW_MODES: ReviewModeConfig[] = [
  { mode: 'quick', persona_count_range: [3, 3], cross_examination: false, calibration: false, description: '快速初筛，5分钟内出结果' },
  { mode: 'standard', persona_count_range: [4, 6], cross_examination: true, calibration: false, description: '日常评审，平衡速度和深度' },
  { mode: 'full', persona_count_range: [6, 8], cross_examination: true, calibration: true, description: '正式评审，完整流程' },
]

export const TASK_TYPES: TaskType[] = [
  { id: 'concept_review', name: '概念评审', description: '核心循环、差异化、可行性', icon: '💡', category: 'development', IconComponent: Lightbulb, stance_enum: ['值得推进', '不值得', '观望'], score_dimensions: ['differentiation', 'retention_potential', 'aesthetic_coherence'] },
  { id: 'demo_first_play', name: 'Demo首玩', description: '上手摩擦、手感、首15分钟体验', icon: '⚙️', category: 'development', IconComponent: Settings, stance_enum: ['继续试玩', '退出', '观望'], score_dimensions: ['retention_potential', 'onboarding_friendliness', 'moment_to_moment_feel'] },
  { id: 'devlog_review', name: '开发日志评审', description: '叙事节奏、透明度、社区反馈', icon: '📖', category: 'development', IconComponent: BookOpen, stance_enum: ['增强期待', '降低期待', '无影响'], score_dimensions: ['narrative_rhythm', 'transparency', 'community_feedback'] },
  { id: 'update_announcement_review', name: '更新公告', description: '版本日志、信任强化、留存信号', icon: '🎯', category: 'development', IconComponent: Target, stance_enum: ['增强信心', '降低信心', '无影响'], score_dimensions: ['communication_clarity', 'trust_reinforcement', 'retention_signal'] },
  { id: 'monetization_review', name: '商业化评审', description: '定价、付费边界、价值感知', icon: '💰', category: 'operations', IconComponent: Coins, stance_enum: ['会买', '不买', '观望'], score_dimensions: ['value_for_money', 'fairness', 'transparency'] },
  { id: 'steam_page_review', name: 'Steam页评审', description: '商店页信息架构、视觉传达、信任信号', icon: '🏪', category: 'operations', IconComponent: Store, stance_enum: ['加愿望单', '不加', '观望'], score_dimensions: ['differentiation', 'value_for_money', 'wishlist_appeal'] },
  { id: 'kickstarter_review', name: '众筹页评审', description: '众筹页叙事、回报设计、信任建立', icon: '🚀', category: 'operations', IconComponent: Rocket, stance_enum: ['会支持', '不会', '观望'], score_dimensions: ['narrative_strength', 'reward_value', 'trust_signals'] },
  { id: 'localization_review', name: '本地化评审', description: '文化适配、语言质量、UI适配', icon: '🌐', category: 'operations', IconComponent: Globe, stance_enum: ['文化适配良好', '存在问题', '观望'], score_dimensions: ['cultural_adaptation', 'language_quality', 'ui_adaptation'] },
  { id: 'discord_community_review', name: '社区运营评审', description: '社区氛围、互动设计、用户留存', icon: '💬', category: 'community', IconComponent: MessageCircle, stance_enum: ['会加入', '不会', '观望'], score_dimensions: ['community_vibe', 'engagement_design', 'retention_signal'] },
  { id: 'looking_for_party_post', name: '找搭子帖', description: '社区文案、传播性、社交吸引力', icon: '👥', category: 'community', IconComponent: Users, stance_enum: ['会转发', '不会', '观望'], score_dimensions: ['social_appeal', 'friction_to_join', 'shareability'] },
  // 下面 4 条的 stance_enum / score_dimensions 曾与后端注册表不一致（前端自造了一套
  // 「有价值/价值有限」「会购买」「顺利上手」「值得投入」，维度也对不上）。评审照样能跑
  // ——前端只把 task_type 的 id 发给后端，引擎用的是自己那份词表——所以不报错，
  // 只是**界面在向用户承诺一套它不会兑现的东西**：选「会不会买」得到的报告里写着「会付费」，
  // 报告页按维度渲染时还会整列对不上。以后端 app/services/TASK_TYPES 为唯一准绳。
  // 防再次漂移的卡口见 web/backend/tests/test_task_type_parity.py。
  { id: 'product_feedback_review', name: '产品反馈评审', description: '通用产品反馈收集与解读，不限游戏', icon: '💬', category: 'product', IconComponent: MessageSquareText, stance_enum: ['会继续用', '会流失', '观望'], score_dimensions: ['usability', 'value_perception', 'trust_signals'] },
  { id: 'pricing_page_review', name: '定价页评审', description: '定价分层、价值传达、信任信号，不限游戏', icon: '🏷️', category: 'product', IconComponent: Tag, stance_enum: ['会付费', '不会', '观望'], score_dimensions: ['value_for_money', 'pricing_clarity', 'trust_signals'] },
  { id: 'onboarding_review', name: '新手引导评审', description: '首次使用体验、上手摩擦，不限游戏', icon: '🧭', category: 'product', IconComponent: Compass, stance_enum: ['会留下', '会放弃', '观望'], score_dimensions: ['onboarding_friendliness', 'time_to_value', 'clarity'] },
  { id: 'pitch_review', name: '创业项目评审', description: 'BP/路演/申报表，投资人与尽调视角，不限行业', icon: '💼', category: 'product', IconComponent: Briefcase, stance_enum: ['值得跟进', '不投', '观望'], score_dimensions: ['market_potential', 'team_credibility', 'evidence_quality'] },
]

export interface TaskTypeCategory {
  id: string
  name: string
  description: string
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>
}

export interface PackCategory {
  id: string
  name: string
  description: string
  icon: string
}

export const TASK_TYPE_CATEGORIES: TaskTypeCategory[] = [
  { id: 'development', name: '开发阶段', description: '游戏开发各阶段的评审', icon: FolderOpen },
  { id: 'operations', name: '运营阶段', description: '发行运营相关评审', icon: TrendingUp },
  { id: 'community', name: '社区阶段', description: '社区与玩家互动评审', icon: Users },
  { id: 'product', name: '通用产品', description: '不限游戏的通用产品评审', icon: Compass },
]

export const PACK_CATEGORIES: PackCategory[] = [
  { id: 'player-type', name: '玩家类型', description: '按玩家特征分类', icon: '🎮' },
  { id: 'platform', name: '平台特性', description: '按平台/设备分类', icon: '🖥️' },
  { id: 'special', name: '特殊用途', description: '特定场景用途', icon: '⭐' },
  { id: 'general', name: '通用用户', description: '不限游戏的通用用户角度', icon: '🧑‍💼' },
]

// 这里原本有 PERSONA_PACKS / MOCK_PERSONAS / MOCK_REPORT / MOCK_REVIEWS 四块演示数据，已删除。
// 删而不是修的理由：PERSONA_PACKS 的 persona_count 写死为 19/12/12/9…，与 src/personas/*.yaml
// 的真实条数几乎条条不符，还漏了真实存在的 launch-compliance 包；MOCK_* 则是整套编造的
// 角色、评审与报告（含风险等级、成本、校准分）。四块当时全仓零引用，真实数据由
// /api/personas/packs 与评审接口提供。留着的风险不是现在显示错，而是它们长得像事实源，
// 下一个人顺手拿来做「N 个角色」「示例报告」就会把假数字推到界面上。

// persona_count 已从本类型中移除。它曾经写死为 6/8/5/10 并直接显示给用户，
// 而 persona_generate 标的 10 超过了所有评审模式的人数上限 8（见下方 REVIEW_MODES），
// 也就是一个可以被当场证伪的数。真正决定人数的是评审模式的 persona_count_range，
// 与技能无关，所以这里根本没有正确值可填——删掉字段而不是改个"对一点"的数，
// 才能保证它不会被谁顺手加回来。
// task_types 的取值来源说明（改前必读）：
// 后端对「技能 × 任务类型」没有任何约束——apply_skill_hint 只是往 materials 里插一条提示语，
// POST /api/v2/reviews 也不校验组合（web/backend/app/services/__init__.py:731-742）。
// 但这份常量此前是手写枚举，四个技能的并集只有 12 项，漏掉 looking_for_party_post 与
// pitch_review；而 CreateReviewPage 用它过滤任务类型列表、SkillSelectPage 用它长度报
// 「可选任务类型（N）」。结果是：用户从技能中心带着 skill 进来，后端完全接受的任务类型
// 被界面藏起来，用户以为「这个技能不支持我要的」而放弃——一条编出来的约束真的拦住了人。
//
// 这里不删字段（CreateReviewPage:59/114 与 SkillSelectPage:126 都在读，删了会编译不过，
// 且那两个文件由别的 agent 负责），改为从 TASK_TYPES 派生全量 id：
// 「不限制」才是可追溯到后端事实的值，N 也就等于真实任务类型总数。
// 真值应从后端取：GET /api/skills/{skill_type} 正在补 task_types 字段，
// 接口可用后前端应改为消费接口数据，本常量只作离线兜底与图标/配色等展示装饰。
const ALL_TASK_TYPE_IDS: string[] = TASK_TYPES.map((t) => t.id)

export const SKILLS: { type: SkillType; name: string; description_zh: string; icon: string; task_types: string[]; use_cases: string[]; color: string; bg: string; border: string }[] = [
  {
    type: 'synthetic_playtest',
    name: '合成试玩',
    description_zh: '模拟真实玩家试玩体验，从上手到深度体验全流程评估，发现设计盲点与体验断裂',
    icon: '/skills/skill-game.png',
    task_types: ALL_TASK_TYPE_IDS,
    use_cases: ['新概念验证', 'Demo首玩测试', '版本更新体验评估', '核心循环验证'],
    color: 'text-brand-primary',
    bg: 'bg-brand-primary/10',
    border: 'border-brand-primary/30',
  },
  {
    type: 'audience_panel',
    name: '受众面板',
    description_zh: '组建目标受众虚拟焦点小组，收集不同人群的真实反应与偏好，量化市场接受度',
    icon: '/skills/skill-audience.png',
    task_types: ALL_TASK_TYPE_IDS,
    use_cases: ['商店页优化', '众筹页评估', '广告效果预测', '落地页转化分析'],
    color: 'text-brand-primary',
    bg: 'bg-brand-primary/10',
    border: 'border-brand-primary/30',
  },
  {
    type: 'red_team_audience',
    name: '红队对抗',
    description_zh: '用对抗性视角主动攻击产品弱点，模拟最挑剔的用户和恶意场景，暴露隐藏风险',
    icon: '/skills/skill-redteam.png',
    task_types: ALL_TASK_TYPE_IDS,
    use_cases: ['付费模型压力测试', '社区危机预演', '本地化文化风险', '公关危机模拟'],
    color: 'text-brand-primary',
    bg: 'bg-brand-primary/10',
    border: 'border-brand-primary/30',
  },
  {
    type: 'persona_generate',
    name: '人格生成',
    // 如实写：后端 _SKILL_PROMPT_HINTS 没给 persona_generate 提示语，选它创建评审
    // 跑出来的就是一次普通评审，不会生成任何人格（skill_type 只被落库当标签）。
    // 真正生成人格的是 POST /api/generate-personas，需要一个独立入口，不该从「创建评审」进。
    // 文案先止损——继续写「自动生成定制化人格」等于让用户花一次评审额度买一个不存在的东西。
    description_zh: '定制人格生成能力（暂未接入评审流程）。从这里创建的评审走的是标准流程，不会额外生成人格。',
    icon: '/skills/skill-persona.png',
    task_types: ALL_TASK_TYPE_IDS,
    use_cases: ['特定人群定制', '边缘用户覆盖', '跨文化人格', '特殊需求用户'],
    color: 'text-brand-primary',
    bg: 'bg-brand-primary/10',
    border: 'border-brand-primary/30',
  },
]

// id 必须逐字等于后端 evaluation_service.RUBRIC_DIMENSIONS（web/backend/app/services/
// evaluation_service.py:17-26）。此前这里写的是另一套自造 id（coverage / depth / consistency /
// evidence_quality / bias_detection / novelty / ethical_safety，只有 actionability 巧合重合），
// 于是 EvaluationPage / ReportPage 的 `find(d => d.id === r.dimension)` 几乎永远 undefined：
// 雷达图轴标签和维度卡片标题退化成英文 snake_case 直出（中文界面里出现 persona_differentiation），
// 说明文字则整行空白。这不是排版问题，是「查不到就静默降级」把缺失伪装成了正常渲染。
//
// name / description 是给这 8 个 id 配的中文标签，语义对齐后端 RUBRIC_SCORES 里 3 分档的描述，
// 不引入后端没有的判分口径。评分和是否通过一律来自接口，本表不参与任何计算。
// 权威词表是 GET /api/rubric（api.ts:322 的 fetchRubric），接上后这里应退化为纯离线兜底。
// 防漂移的卡口见 web/backend/tests/test_frontend_constants_parity.py。
export const EVALUATION_DIMENSIONS: { id: string; name: string; description: string }[] = [
  { id: 'persona_differentiation', name: '人格差异度', description: '各人格是否有由行为规则支撑的稳定视角差异，而不只是措辞不同' },
  { id: 'input_grounding', name: '材料贴合度', description: '结论是否持续引用你提交的材料细节，而不是给一段通用建议' },
  { id: 'actionability', name: '可行动性', description: 'P0/P1/P2 行动项是否具体且分了优先级，而不是泛泛而谈' },
  { id: 'segment_conflict', name: '人群分歧', description: '不同人群之间是否出现了能影响产品决策的真实分歧' },
  { id: 'risk_detection', name: '风险识别', description: '是否指出了明确的阻断点、反对理由和分人群的风险' },
  { id: 'ethical_persona_use', name: '人格伦理', description: '是否避免刻板印象，把人口统计/MBTI 一类字段只当作弱修饰' },
  { id: 'report_structure', name: '报告结构', description: '报告是否包含全部必需章节且每节都有实质内容' },
  { id: 'calibration_honesty', name: '结论诚实度', description: '是否把发现表述为待验证的假设并给出真实验证方式，而非预测成功' },
]
