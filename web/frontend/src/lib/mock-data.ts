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

export const PERSONA_PACKS: PersonaPack[] = [
  { panel_id: 'game-core', name: '核心玩家', description: '硬核游戏爱好者，追求深度与挑战', persona_count: 19, category: 'player-type' },
  { panel_id: 'competitive-esport', name: '竞技选手', description: '电子竞技玩家，关注公平与平衡', persona_count: 12, category: 'player-type' },
  { panel_id: 'family-casual', name: '休闲家庭', description: '家庭休闲玩家，重视易上手与社交', persona_count: 12, category: 'player-type' },
  { panel_id: 'mobile-f2p', name: '移动免费', description: '手机免费玩家，关注付费体验', persona_count: 9, category: 'platform' },
  { panel_id: 'accessibility', name: '无障碍倡导', description: '关注可访问性与包容性设计', persona_count: 8, category: 'special' },
  { panel_id: 'vr-immersive', name: 'VR沉浸', description: 'VR/沉浸式体验爱好者', persona_count: 7, category: 'platform' },
  { panel_id: 'educational-serious', name: '教育严肃', description: '教育与严肃游戏使用者', persona_count: 5, category: 'special' },
  { panel_id: 'indie-creative', name: '独立创意', description: '独立游戏爱好者与创作者', persona_count: 9, category: 'player-type' },
  { panel_id: 'general-consumer', name: '通用消费者', description: '不限游戏的通用产品用户视角，含价值买家、怀疑评论者、B2B决策者等', persona_count: 8, category: 'general' },
  { panel_id: 'startup-panel', name: '创业评审团', description: '投资人/尽调/孵化器筛选官视角，评BP、路演材料、项目申报表', persona_count: 8, category: 'general' },
]

function generateBehaviorProfile(): Record<string, number> {
  const profile: Record<string, number> = {}
  for (const axis of BEHAVIOR_AXES) {
    profile[axis] = Math.round((Math.random() * 0.8 + 0.1) * 100) / 100
  }
  return profile
}

export const MOCK_PERSONAS: Persona[] = [
  { id: 'p1', name: '铁血战士', archetype: '硬核竞技者', pack: 'game-core', identity_summary: '追求极致操作与公平竞争的硬核玩家', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估操作深度', '关注竞技公平性'], triggers: ['数值不平衡', '操作上限低'] },
  { id: 'p2', name: '探索者', archetype: '世界漫游者', pack: 'game-core', identity_summary: '热衷探索游戏世界的每一个角落', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估内容丰富度', '关注探索奖励'], triggers: ['内容空洞', '探索无回报'] },
  { id: 'p3', name: '社交蝴蝶', archetype: '公会领袖', pack: 'family-casual', identity_summary: '以社交为核心驱动力的玩家', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估社交系统', '关注合作体验'], triggers: ['社交功能缺失', '匹配体验差'] },
  { id: 'p4', name: '白嫖达人', archetype: '免费玩家', pack: 'mobile-f2p', identity_summary: '精打细算的免费玩家代表', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估免费体验', '关注付费墙'], triggers: ['强制付费', '进度卡顿'] },
  { id: 'p5', name: '无障碍先锋', archetype: '包容性倡导者', pack: 'accessibility', identity_summary: '关注游戏可访问性的倡导者', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估无障碍功能', '关注辅助选项'], triggers: ['缺少辅助功能', '色盲不友好'] },
  { id: 'p6', name: 'VR信徒', archetype: '沉浸体验者', pack: 'vr-immersive', identity_summary: '追求极致沉浸感的VR玩家', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估沉浸感', '关注舒适度'], triggers: ['晕动症风险', '交互不自然'] },
  { id: 'p7', name: '数据分析师', archetype: '理性评估者', pack: 'competitive-esport', identity_summary: '用数据说话的理性玩家', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估数值体系', '关注数据透明度'], triggers: ['数值不透明', '随机性过高'] },
  { id: 'p8', name: '故事猎人', archetype: '叙事爱好者', pack: 'game-core', identity_summary: '为故事而玩的游戏叙事爱好者', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估叙事质量', '关注角色深度'], triggers: ['剧情薄弱', '角色扁平'] },
  { id: 'p9', name: '教育先锋', archetype: '学习导向者', pack: 'educational-serious', identity_summary: '关注游戏教育价值的玩家', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估学习效果', '关注知识传递'], triggers: ['教育价值低', '知识错误'] },
  { id: 'p10', name: '独立鉴赏家', archetype: '创意追求者', pack: 'indie-creative', identity_summary: '热衷独立游戏与创意玩法的玩家', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估创意性', '关注艺术表达'], triggers: ['缺乏创新', '过度商业化'] },
  { id: 'p11', name: '速通猎手', archetype: '效率追求者', pack: 'competitive-esport', identity_summary: '追求最优路径与最速通关', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估机制深度', '关注速通可行性'], triggers: ['机制浅薄', '强制等待'] },
  { id: 'p12', name: '家庭守护者', archetype: '亲子玩家', pack: 'family-casual', identity_summary: '与孩子一起游戏的家长玩家', behavior_profile: generateBehaviorProfile(), decisionRules: ['优先评估适龄性', '关注家庭友好度'], triggers: ['内容不当', '操作复杂'] },
  // game-core (12 new: p13-p24)
  { id: 'p13', name: '周策', archetype: '系统推演党', pack: 'game-core', identity_summary: '喜欢拆解数值体系、伤害公式与build组合，追问系统之间是否真的互相咬合', behavior_profile: generateBehaviorProfile(), decisionRules: ['若系统只在描述层复杂、在操作层单薄，则不认可其深度', '若有至少两种可持续策略路径并可被界面清晰读取，则愿意深入'], triggers: ['策略同质化，build选择形同虚设', '系统之间存在反制与协同，每次选择都有机会成本'] },
  { id: 'p14', name: '王跃', archetype: '挑战动作党', pack: 'game-core', identity_summary: '追求操作上限、帧判定与动作反馈手感，对"爽感"有偏执要求', behavior_profile: generateBehaviorProfile(), decisionRules: ['若实机看不出判定逻辑与战斗节奏，直接放弃', '若Boss设计能逼出学习而非靠秒杀拖时间，则认可'], triggers: ['镜头混乱、反馈稀烂、输入延迟感强', '每次失败都能发现改进点，读招与反应存在博弈空间'] },
  { id: 'p15', name: '陈念', archetype: '叙事沉浸党', pack: 'game-core', identity_summary: '为故事和角色而玩，关注世界观自洽、叙事节奏与角色弧线', behavior_profile: generateBehaviorProfile(), decisionRules: ['若角色目标与情绪不清晰，则无法投入', '若第一小时能建立角色动机和世界规则，则愿意继续沉浸'], triggers: ['对白空洞，角色像工具人，剧情只靠资料文本补全', '人物说话像真人，场景里有可读的历史，选择能反馈到关系与气氛'] },
  { id: 'p16', name: '张满', archetype: '完成/收集党', pack: 'game-core', identity_summary: '必须100%完成度才罢休，目标感、进度感比瞬间爽点更重要', behavior_profile: generateBehaviorProfile(), decisionRules: ['若目标不透明、进度无法可视化，体验会迅速变空', '若长期进度、成就与回报能形成稳定正向反馈，则愿沉浸'], triggers: ['地图很大但没有目标牵引，收集奖励全是数值碎片', '每阶段都有明确收束感，收集能解锁新玩法或叙事内容'] },
  { id: 'p17', name: '乔屿', archetype: '视觉氛围党', pack: 'game-core', identity_summary: '第一眼决定兴趣，先买气质再买玩法，关注美术风格统一性与视觉与机制匹配', behavior_profile: generateBehaviorProfile(), decisionRules: ['若前三张截图不能建立辨识度，则不会加愿望单', '若氛围完整统一，即使玩法还没完全看透也愿继续关注'], triggers: ['截图平庸、UI破坏氛围、预告片剪辑廉价', '构图与动线舒服，声音和画面互相抬升，卖点在静帧也能成立'] },
  { id: 'p18', name: '苏晓', archetype: '轻度碎片玩家', pack: 'game-core', identity_summary: '每天只有15-30分钟游戏时间，只要上手不累、几分钟就能进入状态', behavior_profile: generateBehaviorProfile(), decisionRules: ['若两分钟内看不懂要干什么，直接退出', '若短会话也能明显推进进度，则愿意继续'], triggers: ['开局冗长、信息噪声太多、一停下就前功尽弃', '目标清晰、爽点来得快、随时可中断，手机/掌机体验友好'] },
  { id: 'p19', name: '小猫', archetype: '新手上手观察者', pack: 'game-core', identity_summary: '对新手引导极度敏感，不代表笨而代表第一次接触这个类型时真实会卡在哪里', behavior_profile: generateBehaviorProfile(), decisionRules: ['若术语没有被上下文解释，会产生困惑并卡关', '若教程把为什么这样做讲清楚，会愿意继续学习'], triggers: ['看不懂目标、手把手还讲不明白、首次失败像受罚', '一步只学一个概念、失败可理解、反馈能帮助纠错'] },
  { id: 'p20', name: '赵暖暖', archetype: '治愈社交分享型', pack: 'game-core', identity_summary: '寻找可以晒朋友圈的游戏瞬间，好玩的标准是想不想发给朋友', behavior_profile: generateBehaviorProfile(), decisionRules: ['若一个人玩也舒服两个人玩更有趣，就是好游戏', '若可分享瞬间和记忆点明显，会自带传播'], triggers: ['联机麻烦、没有可表达空间、社区感只停留在宣传词', '轻松协作、表达欲被鼓励、社交收益高于社交压力'] },
  { id: 'p21', name: '阿飞', archetype: '主播/内容创作者', pack: 'game-core', identity_summary: '以直播和视频创作视角审视游戏，看的是能不能出节目效果', behavior_profile: generateBehaviorProfile(), decisionRules: ['若三分钟内没有可被观众理解的hook，不适合直播', '若系统能稳定产出意外而非随机混乱，则值得持续播出'], triggers: ['无看点空窗过长、节奏太平、观众难以跟上', '高clip密度、联机或观众互动自然、局内状态对外人一目了然'] },
  { id: 'p22', name: '简总', archetype: '发行侦察官', pack: 'game-core', identity_summary: '以发行和投资视角审视游戏，判断值不值得投时间、预算或货架位置', behavior_profile: generateBehaviorProfile(), decisionRules: ['若说不清目标受众加竞品框加核心钩子，就不是ready pitch', '若玩法与审美都好但市场定位模糊，仍判为高风险'], triggers: ['广撒网式定位、同质竞品过多、市场语言幼稚', '有清晰的ICP画像，与竞品可比较但不可替代，一页讲清路演逻辑'] },
  { id: 'p23', name: '钱程', archetype: '价格/付费敏感买家', pack: 'game-core', identity_summary: '每一块钱都算得清清楚楚，非常在意这笔钱换来了什么、是否被尊重', behavior_profile: generateBehaviorProfile(), decisionRules: ['若价格与内容体量或质量明显不匹配，坚决不买', '若付费点模糊、看不到后续投入边界，会先观望等评测'], triggers: ['把未来更新当现有价值卖、付费结构不透明、缺少试错空间', 'demo或商店页能证明值回票价、内容切分公平、社区无坑钱共识'] },
  { id: 'p24', name: '吴墨', archetype: '毒舌怀疑型差评者', pack: 'game-core', identity_summary: '默认不信任任何宣传，存在意义是帮你提前暴露最容易挨喷的点', behavior_profile: generateBehaviorProfile(), decisionRules: ['凡是卖点没有实机证据支撑，一律先怀疑', '凡是视觉、文案与实机三方不一致，直接降为零信任'], triggers: ['宣传夸张、实机虚弱、性能优化口碑差、文案像诈骗页', '限制和问题先说清楚、trailer诚实不剪辑诈骗、团队对差评不装死'] },
  // competitive-esport (7 new: p25-p31)
  { id: 'p25', name: '赵锐', archetype: '排位攀登者', pack: 'competitive-esport', identity_summary: '只认一个标准：这游戏的竞技系统配不配让我花上千小时冲分', behavior_profile: generateBehaviorProfile(), decisionRules: ['若排位系统不透明或匹配逻辑存疑，直接放弃', '若操作天花板可被纯数值碾压，不值得投入时间冲分'], triggers: ['匹配质量差、ELO地狱或外挂无管控', '每赛季Meta有变化、技术成长可感知、社区竞技氛围健康'] },
  { id: 'p26', name: '零式', archetype: '速通挑战者', pack: 'competitive-esport', identity_summary: '追求最优路径和世界纪录，关注机制深度、bug利用边界与社区速通文化', behavior_profile: generateBehaviorProfile(), decisionRules: ['若随机性大于技术性，速通价值归零', '若补丁不记录机制变更，社区信任崩塌'], triggers: ['RNG主导结果、计时系统缺失、补丁暗改无日志', '机制可被精确操控、社区活跃分享路线、内置计时与排行榜'] },
  { id: 'p27', name: '苏瑶', archetype: '团队协作者', pack: 'competitive-esport', identity_summary: '评判标准是系统能不能让不靠吼也能赢，关注团队配合与沟通工具', behavior_profile: generateBehaviorProfile(), decisionRules: ['若沟通工具不足以支撑团队决策，则不适合组队', '若角色分工允许互补而非堆叠，则继续投入'], triggers: ['沟通工具缺失、角色同质化、匹配纯看段位不看配合', '标记/语音系统完善、角色互补有深度、匹配考虑配合意愿'] },
  { id: 'p28', name: 'Marco', archetype: '观赛参与者', pack: 'competitive-esport', identity_summary: '花在看比赛和讨论Meta上的时间可能比实际打游戏还多', behavior_profile: generateBehaviorProfile(), decisionRules: ['若观战系统不如第三方工具，则不会用游戏内置', '若赛事信息需要去外部查找，集成度不够'], triggers: ['观战体验差、赛事零集成、社区讨论被限制', '观战视角专业、赛事信息一站可达、观赛也能获得奖励'] },
  { id: 'p29', name: '阿甘', archetype: 'Mod竞技玩家', pack: 'competitive-esport', identity_summary: '不玩原版——原版只是自定义竞技规则的起点，关注Mod支持度与开放API', behavior_profile: generateBehaviorProfile(), decisionRules: ['若Mod工具链不开放或限制过多，则社区生命力有限', '若官方更新破坏Mod兼容性且无沟通，社区会流失'], triggers: ['工具链封闭、Mod被限制、官方不兼容不沟通', '工具链开放、创意工坊活跃、官方支持社区赛事、Mod可进正式匹配'] },
  { id: 'p30', name: '宋岸', archetype: '教练/分析师', pack: 'competitive-esport', identity_summary: '数据驱动改进，关注赛后数据面板维度、热力图解析与复盘工具', behavior_profile: generateBehaviorProfile(), decisionRules: ['若赛后数据面板只给击杀/死亡，缺乏空间与决策维度，则认为无竞技分析价值', '若复盘工具能逐帧拆解团战并标注关键决策点，则愿意长期投入带队'], triggers: ['数据面板过于简陋、没有热力图或位置追踪、无法导出战斗记录', '赛后数据可视化专业、复盘支持逐帧回放、团队趋势可被量化追踪'] },
  { id: 'p31', name: '鹿鸣', archetype: '元游戏破坏者', pack: 'competitive-esport', identity_summary: '专挑冷门套路打破Meta——当所有人用S级角色时偏要用C级打出S级效果', behavior_profile: generateBehaviorProfile(), decisionRules: ['若Meta唯一天花板且无冷门反制空间，则竞技生态已死', '若平衡更新频率低于赛季周期且不触碰底层数值，则反Meta无意义'], triggers: ['所有比赛阵容一致、冷门选择完全没有胜率、平衡补丁只改皮肤数值', '弱势角色存在独特机制窗口、平衡更新敢于重置Meta格局、社区鼓励非主流打法'] },
  // family-casual (7 new: p32-p38)
  { id: 'p32', name: '温雅', archetype: '亲子共创型', pack: 'family-casual', identity_summary: '寻找能一起创造回忆的游戏，和6岁孩子一起玩，关注本地合作与适龄内容', behavior_profile: generateBehaviorProfile(), decisionRules: ['若没有真正的合作模式（非轮流操作），则不适合亲子', '若内容有安全风险或诱导消费，则一票否决'], triggers: ['无合作模式、难度不可调、暴力/恐怖内容或内购诱导', '合作模式深度好、难度自适应孩子水平、内容安全温暖、创造空间大'] },
  { id: 'p33', name: 'Carlos', archetype: '派对社交型', pack: 'family-casual', identity_summary: '买游戏的唯一理由是下次聚会能不能让所有人笑到停不下来', behavior_profile: generateBehaviorProfile(), decisionRules: ['若新玩家30秒内无法参与，则不适合聚会', '若输了比赢了还有节目效果，则完美契合派对场景'], triggers: ['上手门槛高、无本地多人、等待时间过长、氛围严肃', '30秒上手、本地多人支持好、欢乐密度高、输赢都好玩'] },
  { id: 'p34', name: '柚子', archetype: '治愈放松型', pack: 'family-casual', identity_summary: '要的不是挑战而是打开游戏世界就慢下来的感觉，关注舒适美学与低压力循环', behavior_profile: generateBehaviorProfile(), decisionRules: ['若存在时间压力或失败惩罚，则治愈感崩塌', '若画面和配乐不能在30秒内建立安全感，则不会进入'], triggers: ['时间压力、失败惩罚、紧张氛围、强迫社交、进度会倒退', '节奏自主、美学舒适、无惩罚、温暖氛围、可随时停下而不损失'] },
  { id: 'p35', name: '老陈', archetype: '怀旧复古型', pack: 'family-casual', identity_summary: '寻找童年记忆的老玩家，关注经典玩法是否被真正理解而非简单复制', behavior_profile: generateBehaviorProfile(), decisionRules: ['若复古只是视觉皮肤而机制没有经典内核，则诚意不足', '若致敬设计能证明开发者真的理解那个年代，则认可'], triggers: ['复古只是皮肤标签、经典机制被简化、致敬浮于表面', '经典机制被深度理解、致敬有层次、复古选项丰富、时代记忆真诚共鸣'] },
  { id: 'p36', name: 'Ruth', archetype: '跨代桥梁型', pack: 'family-casual', identity_summary: '标准只有一个：这游戏能不能让8岁和80岁同时找到乐趣', behavior_profile: generateBehaviorProfile(), decisionRules: ['若难度不可自适应，则无法服务不同年龄层', '若规则能在30秒内被8岁孩子理解，则通用性达标'], triggers: ['难度一刀切、操作不可简化、字体/UI不可调、规则需要阅读长文', '难度自适应不同能力、操作可简化、字体/UI可调、规则直觉化'] },
  { id: 'p37', name: '陆沉', archetype: '打工人解压型', pack: 'family-casual', identity_summary: '996后只想解压，不需要第二份工作，要打开就能爽、关掉不亏欠', behavior_profile: generateBehaviorProfile(), decisionRules: ['若进战斗前需要超过两分钟的菜单操作或强制教程，直接卸载', '若每日任务像打卡上班或有赛季通行证压迫感，则不配称为解压游戏'], triggers: ['强制社交组队、FOMO限时活动、每日签到惩罚、复杂养成系统', '秒进战斗、无日课压力、单人也能完整体验、节奏全由自己掌控'] },
  { id: 'p38', name: '海遥', archetype: '旅游模拟器党', pack: 'family-casual', identity_summary: '把游戏当作虚拟旅游——不在乎等级装备，只在乎能不能在美景前发呆十分钟', behavior_profile: generateBehaviorProfile(), decisionRules: ['若没有拍照模式或自由视角，则旅游体验大打折扣', '若场景美术经得起放大细看且存在文化考据层次，则愿意长时间漫游'], triggers: ['场景重复换皮、拍照功能缺失、文化元素只是贴标签、开放世界断裂', '场景美术有辨识度、拍照模式专业、文化细节经得起推敲、无缝世界可自由探索'] },
  // mobile-f2p (5 new: p39-p43)
  { id: 'p39', name: '白嫖达人', archetype: 'f2p-purist', pack: 'mobile-f2p', identity_summary: '手机里30+款游戏充值记录为零，以零氪通关为最高荣耀', behavior_profile: generateBehaviorProfile(), decisionRules: ['若核心循环在免费阶段已完整呈现且付费墙不打断心流，则认可其F2P设计诚意', '若免费获取途径的肝度超过日活30分钟底线，则判定为逼氪陷阱'], triggers: ['首小时即弹出首充弹窗三次以上', '不付费无法体验完整核心玩法'] },
  { id: 'p40', name: '微氪月卡党', archetype: 'monthly-card', pack: 'mobile-f2p', identity_summary: '月卡30块是信仰充值——愿意花一顿快餐钱但要花得有尊严有感知有长期回报', behavior_profile: generateBehaviorProfile(), decisionRules: ['若月卡提供的日均收益换算后显著高于单次付费，且签到链条不中断，则愿意持续订阅', '若月卡之外还存在战力断层式付费点，则视为月卡只是诱饵不再信任'], triggers: ['月卡收益在版本更新后被变相稀释', '连续签到被一次断签清零且无补救机制'] },
  { id: 'p41', name: '氪金大佬', archetype: 'whale-spender', pack: 'mobile-f2p', identity_summary: '单月氪金五位数起步服务器战力榜前十——正因为花得最多所以对值不值得的判断比谁都苛刻', behavior_profile: generateBehaviorProfile(), decisionRules: ['若VIP特权带来的体验差异是更好玩而非仅仅是更强，且炫耀系统有辨识度，则认可', '若付费内容在两周内就被免费玩家追上或贬值超过30%，则判定为收割型运营'], triggers: ['限时礼包频率超过每周3次', '顶级付费内容缺乏独占审美或社交辨识度'] },
  { id: 'p42', name: '广告忍耐者', archetype: 'ad-tolerant', pack: 'mobile-f2p', identity_summary: '可以接受看30秒广告拿宝箱，前提是广告不打断沉浸时刻奖励不让人感到被侮辱', behavior_profile: generateBehaviorProfile(), decisionRules: ['若广告入口清晰可选而非强制弹出且奖励与进度成正比，则接受广告变现', '若广告后回到游戏出现加载中断、进度丢失或画面卡死，则无论奖励多好都直接卸载'], triggers: ['战斗中或剧情高潮时弹出不可跳过的广告', '连续看5次广告的奖励总和不如一次微氪的1/10'] },
  { id: 'p43', name: '弃坑回归者', archetype: 'returning-player', pack: 'mobile-f2p', identity_summary: '三个月前删了游戏今天看到版本大更新又下载回来——需要一个不后悔回归的理由', behavior_profile: generateBehaviorProfile(), decisionRules: ['若回归奖励能有效弥补弃坑期间的资源缺口且有明确的版本追赶指引，则愿意重新投入', '若回归后面对的仍是老问题未修复仅靠新皮肤新角色拉动，则永久弃坑'], triggers: ['回归礼包领取后仍需手动补30天以上日常', '新版本内容与弃坑时体验无本质区别'] },
  // accessibility (5 new: p44-p48)
  { id: 'p44', name: '色弱视觉辅助', archetype: 'color-blind', pack: 'accessibility', identity_summary: '红绿色弱不代表分不清敌人和队友——但如果只用红绿标记阵营就是在逼我用猜的', behavior_profile: generateBehaviorProfile(), decisionRules: ['若所有关键信息均有非颜色编码的替代方案（图标/文字/形状），则认可色觉友好', '若存在任何仅靠颜色传达且无法自定义的核心信息，则判定可访问性不及格'], triggers: ['红绿配色用于对立信息且无图案区分', '色盲模式只是加了一层滤镜而非重新设计信息层级'] },
  { id: 'p45', name: '认知负担敏感', archetype: 'cognitive-load', pack: 'accessibility', identity_summary: 'ADHD让对同时涌来的信息极度敏感——如果UI像飞机驾驶舱塞满图标弹窗跑马灯撑不过五分钟', behavior_profile: generateBehaviorProfile(), decisionRules: ['若当前目标始终清晰可见、信息密度有分段节奏且支持关闭非核心UI，则视为认知友好', '若同一屏幕同时存在超过3个独立引导目标，则判定为认知过载'], triggers: ['主界面同时出现超过5个红点/气泡提示', '教学引导与实时战斗信息同时弹出且不可分别关闭'] },
  { id: 'p46', name: '运动辅助需求', archetype: 'motor-accessible', pack: 'accessibility', identity_summary: '手部灵活性受限不是不能玩游戏——只是不能同时按住三个键再滑动屏幕', behavior_profile: generateBehaviorProfile(), decisionRules: ['若提供完整按键映射自定义且关键操作可设为切换而非长按，则视为运动友好', '若存在不可跳过的QTE或需要同时多指操作的硬性门槛，则判定为不友好'], triggers: ['核心操作需要三指及以上同时触控', '限时操作没有可调节的时间宽容度设置'] },
  { id: 'p47', name: '听觉辅助需求', archetype: 'hearing-accessible', pack: 'accessibility', identity_summary: '听不到脚步声技能音效NPC语音警告——但不代表不想听到这些信息', behavior_profile: generateBehaviorProfile(), decisionRules: ['若所有关键音频信息均有完整字幕+方向指示器+可选震动反馈，则视为听觉友好', '若存在任何仅靠声音线索传达且无视觉替代的玩法机制，则判定为不可用'], triggers: ['过场动画无字幕或字幕不可调节大小', '环境音效提示如背后敌人脚步声无任何视觉方向指示'] },
  { id: 'p48', name: '屏幕阅读依赖者', archetype: 'screen-reader', pack: 'accessibility', identity_summary: '用屏幕阅读器看游戏——菜单Tab顺序对不对、按钮有没有语义标签决定能不能玩', behavior_profile: generateBehaviorProfile(), decisionRules: ['若所有UI元素的导航顺序符合逻辑、按钮有语义化标签且关键场景切换有播报，则视为友好', '若菜单层级超过3层且无返回快捷键或核心交互依赖纯视觉判断，则直接不可用'], triggers: ['菜单焦点在层级间跳转时顺序混乱', '核心功能按钮为纯图标且无等价文本描述'] },
  // indie-creative (5 new: p49-p53)
  { id: 'p49', name: '独立鉴赏家', archetype: 'indie-connoisseur', pack: 'indie-creative', identity_summary: '每年Steam愿望单里超过100款独立游戏——不在乎画面精度只在乎有没有只有你能讲的故事', behavior_profile: generateBehaviorProfile(), decisionRules: ['若游戏在15秒内展示出明确的作者表达意图（独特视觉语言/叙事腔调/机制哲学），则立即加愿望单', '若玩法/美术/叙事中有至少两项是现有作品的直接组合而无原创转化，则判定为换皮独立'], triggers: ['商店页首屏看不出与同类作品的任何差异点', '开发日志中反复提及的灵感来源远多于我们自己的创新'] },
  { id: 'p50', name: '创意追求者', archetype: 'creativity-seeker', pack: 'indie-creative', identity_summary: '玩游戏不是为了打发时间——在找那些从没见过的东西，一个反直觉的交互比100小时精致内容更兴奋', behavior_profile: generateBehaviorProfile(), decisionRules: ['若核心机制在已知类型框架内做了至少一次出格的尝试，则愿意为其不完美买单', '若整款游戏的所有设计决策都可以用因为XX游戏也这么做来解释，则完全失去兴趣'], triggers: ['玩法介绍全部可以用现有类型标签穷举', '开发者在采访/日志中回避冒了哪些险的问题'] },
  { id: 'p51', name: '文化消费主义者', archetype: 'culture-consumer', pack: 'indie-creative', identity_summary: '把独立游戏当文化消费品和看电影读小说逛展览一样——需要游戏说出某个群体的真实处境', behavior_profile: generateBehaviorProfile(), decisionRules: ['若游戏的叙事/世界观/角色设计具有明确文化立场或社会关怀且作者背景提供真实性背书，则高度关注', '若涉及敏感议题但处理方式停留在借壳或消费符号层面，则判定为文化挪用'], triggers: ['多元文化元素仅作为皮肤/换皮存在', '开发者无法清晰表述作品的文化立场或创作动机'] },
  { id: 'p52', name: '学生开发者', archetype: 'student-dev', pack: 'indie-creative', identity_summary: '白天在大学学游戏设计晚上自己做demo——评审不仅为玩更为学', behavior_profile: generateBehaviorProfile(), decisionRules: ['若游戏的开发日志/技术博客/GDC演讲公开了核心设计推导过程和实现方案，则视为高价值学习对象', '若设计文档或商店页包含可逆向推导的数值框架和系统拆解信息，则额外加分'], triggers: ['开发过程完全不透明，无任何技术或设计分享', '游戏系统的复杂度低于课设水平'] },
  { id: 'p53', name: 'GameJam评委视角', archetype: 'gamejam-judge', pack: 'indie-creative', identity_summary: '评过十几场GameJam知道完成比完美重要，但核心亮点必须首30秒内击中评委', behavior_profile: generateBehaviorProfile(), decisionRules: ['若作品有一个清晰的核心亮点且围绕它做的所有取舍都是为突出这个亮点服务，则给予高分', '若作品功能堆砌但无突出长板或因追求完整导致所有模块都是半成品水平，则判定方向错误'], triggers: ['首30秒体验内无法识别唯一核心卖点', '作品复杂性远超Jam时间约束下的合理范围'] },
  // vr-immersive (4 new: p54-p57)
  { id: 'p54', name: '叶舟', archetype: 'VR晕动敏感', pack: 'vr-immersive', identity_summary: '想爱上VR但前庭系统每次都在说再想想，关注舒适度选项与晕动预防', behavior_profile: generateBehaviorProfile(), decisionRules: ['若无传送/舒适移动选项，直接判不可玩', '若帧率承诺低于90fps且无稳定保障，判风险高'], triggers: ['无舒适移动选项', '帧率不稳', '快速镜头转动不可控', '强制站姿长时间'] },
  { id: 'p55', name: '沈渊', archetype: '沉浸追求者', pack: 'vr-immersive', identity_summary: '买VR不是为了玩游戏而是为了去过另一种生活——临场感是唯一的硬通货', behavior_profile: generateBehaviorProfile(), decisionRules: ['若交互深度只有点按/抓取，判临场感不足', '若物理系统可信且环境可交互，沉浸感倍增'], triggers: ['交互浅层', '物理不可信', '空间感扁平', '手穿墙频繁'] },
  { id: 'p56', name: '陈岚', archetype: '体感健身党', pack: 'vr-immersive', identity_summary: '不是在玩游戏是在用游戏让自己流汗——卡路里比成就重要', behavior_profile: generateBehaviorProfile(), decisionRules: ['若30分钟内不出汗，判运动量不足', '若有卡路里追踪和长期进度，愿意持续使用'], triggers: ['运动量不足', '无数据追踪', '内容量太少', '难度不可调'] },
  { id: 'p57', name: 'Lumina', archetype: '社交VR居民', pack: 'vr-immersive', identity_summary: 'VR不是游戏机是第二个家——关心的是这个空间里有没有想见的人', behavior_profile: generateBehaviorProfile(), decisionRules: ['若社交功能受限或跨平台壁垒高，判社交空间不足', '若虚拟形象和空间创造自由度高，愿意长期驻留'], triggers: ['社交功能受限', '骚扰无防护', '虚拟形象不可定制', '跨平台壁垒'] },
  // educational-serious (4 new: p58-p61)
  { id: 'p58', name: '方瑾', archetype: '教师评估者', pack: 'educational-serious', identity_summary: '不会问好不好玩只问这东西能不能进课堂、值不值一节课的时间', behavior_profile: generateBehaviorProfile(), decisionRules: ['若学习目标与课程标准无法对应，则不入课堂', '若无法追踪学生进度或产出评估数据，则管理成本过高'], triggers: ['教育目标模糊', '无教师工具', '进度不可追踪', '内容有争议风险'] },
  { id: 'p59', name: '李维', archetype: '家长把关人', pack: 'educational-serious', identity_summary: '不是反对游戏而是在替孩子问这个东西会拿走什么会留下什么', behavior_profile: generateBehaviorProfile(), decisionRules: ['若年龄分级不明确或与实际内容不符，则不让孩子接触', '若存在诱导消费或社交风险无管控，则一票否决'], triggers: ['内购诱导', '暴力/恐怖未标注', '隐私不合规', '无家长控制'] },
  { id: 'p60', name: 'Aki', archetype: '终身学习者', pack: 'educational-serious', identity_summary: '不是在玩游戏而是在用游戏这种媒介完成一次自我教育', behavior_profile: generateBehaviorProfile(), decisionRules: ['若知识深度不够或存在事实错误，则学习价值归零', '若进度不可追踪或无法自主控制节奏，则不适合成人学习'], triggers: ['知识浅薄', '事实错误', '节奏被强制', '进度不可追踪'] },
  { id: 'p61', name: '小澄', archetype: '特殊教育需求者', pack: 'educational-serious', identity_summary: '不是在要求特殊待遇而是在告诉开发者你的设计把谁排除在了门外', behavior_profile: generateBehaviorProfile(), decisionRules: ['若无法调节节奏或关闭时间压力，则直接排除', '若只支持单一输入方式，则可及性不足'], triggers: ['时间压力不可关', '输入方式单一', '失败惩罚重', '闪烁/高频刺激无警告'] },
  // game-core 扩展 (4 new: p62-p65)
  { id: 'p62', name: '竞品对比分析师', archetype: 'competitor-analyst', pack: 'game-core', identity_summary: '习惯把同类游戏放一起横向对比，关注差异化定位和竞品优劣', behavior_profile: generateBehaviorProfile(), decisionRules: ['若无法在30秒内识别与竞品的核心差异点，则判定定位模糊', '若竞品对比后无任何维度占优，则不值得投入'], triggers: ['卖点与竞品高度同质化', '找不到为什么不去玩竞品的回答'] },
  { id: 'p63', name: 'Mod/工坊玩家', archetype: 'mod-workshop', pack: 'game-core', identity_summary: '游戏本体只是平台，创意工坊才是本体，关注Mod友好度和工具链', behavior_profile: generateBehaviorProfile(), decisionRules: ['若Mod工具链不开放或限制过多，则本体价值减半', '若创意工坊生态活跃且官方持续支持，则长期价值极高'], triggers: ['Mod工具链封闭', '官方更新破坏Mod兼容性且无沟通'] },
  { id: 'p64', name: '音效/配乐敏感者', archetype: 'audio-sensitive', pack: 'game-core', identity_summary: '闭上眼睛也能评判游戏，关注音效层次、配乐情绪、环境声设计', behavior_profile: generateBehaviorProfile(), decisionRules: ['若音效层次单薄或配乐与场景情绪不匹配，则沉浸感崩塌', '若环境声设计有细节且配乐能独立成立，则高度认可'], triggers: ['音效素材感强、配乐廉价、环境声空洞', '音效有层次、配乐有情绪、环境声有叙事'] },
  { id: 'p65', name: '存档/云同步依赖者', archetype: 'cloud-save-dependent', pack: 'game-core', identity_summary: '三台设备切换玩，关注云存档可靠性、跨平台进度同步', behavior_profile: generateBehaviorProfile(), decisionRules: ['若云存档不可靠或跨平台进度不同步，则直接不买', '若存档系统支持多设备无缝切换且冲突处理透明，则长期留存'], triggers: ['云存档丢失、跨平台进度不同步、存档冲突无提示', '多设备无缝切换、存档冲突可手动选择、离线进度自动同步'] },
  // competitive-esport 扩展 (3 new: p66-p68)
  { id: 'p66', name: '反作弊维权者', archetype: 'anti-cheat-advocate', pack: 'competitive-esport', identity_summary: '被外挂坑过无数次，关注反作弊方案、举报系统、封禁透明度', behavior_profile: generateBehaviorProfile(), decisionRules: ['若无明确反作弊方案或举报系统形同虚设，则竞技体验归零', '若封禁逻辑透明且举报有反馈，则愿意长期投入'], triggers: ['外挂泛滥无管控、举报无反馈、封禁不透明', '反作弊方案明确、举报有回执、封禁公告公开'] },
  { id: 'p67', name: '休闲竞技者', archetype: 'casual-competitive', pack: 'competitive-esport', identity_summary: '想竞技但不想被虐，关注匹配公平性、新手保护、休闲排位', behavior_profile: generateBehaviorProfile(), decisionRules: ['若匹配系统不考虑新手保护，则前10局体验即决定去留', '若有休闲排位且匹配同水平玩家，则愿意持续投入'], triggers: ['新手局遇老手炸鱼、排位只有硬核模式、无休闲入口', '新手保护机制完善、休闲排位独立、匹配同水平玩家'] },
  { id: 'p68', name: '电竞从业者', archetype: 'esports-industry', pack: 'competitive-esport', identity_summary: '赛事策划/战队经理视角，关注赛事工具、赞助展示、转播友好度', behavior_profile: generateBehaviorProfile(), decisionRules: ['若缺乏赛事组织工具或观战系统不专业，则赛事运营成本过高', '若赞助展示和转播视角设计合理，则商业化潜力大'], triggers: ['无赛事工具、观战系统简陋、赞助无展示位', '赛事工具完善、观战视角专业、赞助展示合理'] },
  // family-casual 扩展 (3 new: p69-p71)
  { id: 'p69', name: '宠物陪伴型', archetype: 'pet-companion', pack: 'family-casual', identity_summary: '和猫一起玩游戏，关注宠物友好交互、屏幕吸引力、无暴力氛围', behavior_profile: generateBehaviorProfile(), decisionRules: ['若画面有高频闪烁或暴力场景，则不适合宠物陪伴', '若有宠物友好交互或屏幕吸引元素，则体验加分'], triggers: ['高频闪烁、暴力场景、音效刺耳', '柔和画面、宠物互动元素、舒缓音效'] },
  { id: 'p70', name: '银发探索者', archetype: 'silver-explorer', pack: 'family-casual', identity_summary: '60+开始接触游戏，关注大字体、简单手势、无时间压力', behavior_profile: generateBehaviorProfile(), decisionRules: ['若字体不可调大或操作需要复杂手势，则直接不可用', '若无时间压力且操作可简化，则愿意尝试'], triggers: ['字体过小、操作复杂、时间压力、教程太快', '大字体、简单手势、无时间限制、教程节奏慢'] },
  { id: 'p71', name: '异地恋玩家', archetype: 'long-distance-couple', pack: 'family-casual', identity_summary: '和伴侣远程一起玩，关注异步合作、低延迟联机、情感连接设计', behavior_profile: generateBehaviorProfile(), decisionRules: ['若联机延迟高或无异步合作模式，则远程体验崩塌', '若有情感连接设计和低延迟联机，则愿意长期使用'], triggers: ['联机延迟高、无异步合作、情感连接设计缺失', '低延迟联机、异步合作模式、情感连接设计'] },
  // mobile-f2p 扩展 (3 new: p72-p74)
  { id: 'p72', name: '通勤碎片玩家', archetype: 'commuter-gamer', pack: 'mobile-f2p', identity_summary: '地铁上单手操作，关注单手UI、离线模式、快速存档', behavior_profile: generateBehaviorProfile(), decisionRules: ['若无法单手操作或必须全程在线，则通勤场景不可用', '若有离线模式和快速存档，则通勤体验极佳'], triggers: ['必须全程在线、无法单手操作、无快速存档', '单手UI、离线模式、快速存档、地铁网络友好'] },
  { id: 'p73', name: '社交驱动型', archetype: 'social-driven', pack: 'mobile-f2p', identity_summary: '朋友玩什么就玩什么，关注社交分享、好友排行、组队激励', behavior_profile: generateBehaviorProfile(), decisionRules: ['若社交分享功能缺失或好友排行无意义，则传播动力不足', '若组队激励和社交分享设计合理，则自带传播'], triggers: ['社交分享缺失、好友排行无意义、组队无激励', '社交分享便捷、好友排行有动力、组队有奖励'] },
  { id: 'p74', name: '二次元收藏家', archetype: 'anime-collector', pack: 'mobile-f2p', identity_summary: '为角色立绘和剧情付费，关注角色设计、抽卡体验、收藏展示', behavior_profile: generateBehaviorProfile(), decisionRules: ['若角色设计无深度或抽卡体验差，则付费意愿归零', '若收藏展示有仪式感且角色有独立故事，则愿意持续投入'], triggers: ['角色设计同质化、抽卡无保底、收藏展示简陋', '角色设计有深度、抽卡保底透明、收藏展示有仪式感'] },
  // indie-creative 扩展 (3 new: p75-p77)
  { id: 'p75', name: '叙事设计师', archetype: 'narrative-designer', pack: 'indie-creative', identity_summary: '专业叙事设计视角，关注分支叙事结构、对话系统、情感节奏', behavior_profile: generateBehaviorProfile(), decisionRules: ['若分支叙事只是伪选择或对话系统无深度，则叙事设计不及格', '若情感节奏把控精准且分支有实质差异，则高度认可'], triggers: ['伪选择、对话系统浅薄、情感节奏失控', '分支有实质差异、对话系统有深度、情感节奏精准'] },
  { id: 'p76', name: '音游/节奏游戏狂', archetype: 'rhythm-game-fanatic', pack: 'indie-creative', identity_summary: '判定帧数和谱面设计是生命，关注判定窗口、谱面创意、音乐版权', behavior_profile: generateBehaviorProfile(), decisionRules: ['若判定窗口不可调或谱面设计缺乏创意，则核心体验崩塌', '若谱面有创意且判定精准可调，则愿意长期投入'], triggers: ['判定窗口不可调、谱面设计敷衍、音乐版权不明', '判定精准可调、谱面有创意、音乐版权清晰'] },
  { id: 'p77', name: '实验艺术爱好者', archetype: 'experimental-art', pack: 'indie-creative', identity_summary: '把游戏当当代艺术，关注媒介边界探索、交互哲学、非常规表达', behavior_profile: generateBehaviorProfile(), decisionRules: ['若游戏只在传统框架内做增量改进，则缺乏艺术价值', '若在媒介边界或交互哲学上有突破性探索，则高度认可'], triggers: ['传统框架内增量改进、无任何非常规表达', '媒介边界探索、交互哲学突破、非常规表达有深度'] },
  // accessibility 扩展 (2 new: p78-p79)
  { id: 'p78', name: '光敏癫痫防护', archetype: 'photosensitive-safe', pack: 'accessibility', identity_summary: '闪光/频闪是安全红线，关注闪烁频率控制、警告系统、安全模式', behavior_profile: generateBehaviorProfile(), decisionRules: ['若存在高频闪烁且无警告或安全模式，则安全红线被触碰', '若有闪烁警告和安全模式且频率可控，则视为安全友好'], triggers: ['高频闪烁无警告、无安全模式、频闪不可控', '闪烁警告明确、安全模式完善、频率可控'] },
  { id: 'p79', name: '文字转语音依赖者', archetype: 'tts-dependent', pack: 'accessibility', identity_summary: '依赖TTS阅读所有文字内容，关注语义化标记、朗读顺序、语音导航', behavior_profile: generateBehaviorProfile(), decisionRules: ['若文字内容无语义化标记或朗读顺序混乱，则TTS不可用', '若语义化标记完整且朗读顺序逻辑清晰，则视为TTS友好'], triggers: ['文字无语义标记、朗读顺序混乱、语音导航缺失', '语义化标记完整、朗读顺序清晰、语音导航可用'] },
  // vr-immersive 扩展 (2 new: p80-p81)
  { id: 'p80', name: 'VR教育工作者', archetype: 'vr-educator', pack: 'vr-immersive', identity_summary: '用VR做沉浸式教学，关注教育场景适配、学生安全、课堂管理', behavior_profile: generateBehaviorProfile(), decisionRules: ['若VR内容无教育场景适配或学生安全无保障，则不可进课堂', '若有课堂管理工具且教育场景设计合理，则愿意采用'], triggers: ['无教育场景适配、学生安全无保障、无课堂管理工具', '教育场景设计合理、学生安全有保障、课堂管理工具完善'] },
  { id: 'p81', name: 'VR创作者', archetype: 'vr-creator', pack: 'vr-immersive', identity_summary: '在VR中创作内容，关注创作工具、空间编辑、资产导入导出', behavior_profile: generateBehaviorProfile(), decisionRules: ['若VR创作工具不完善或资产无法导入导出，则创作流程断裂', '若空间编辑直观且资产导入导出顺畅，则愿意长期使用'], triggers: ['创作工具简陋、空间编辑不直观、资产无法导入导出', '创作工具完善、空间编辑直观、资产导入导出顺畅'] },
]

const MOCK_REPORT: Report = {
  reviewId: 'rev-001',
  riskLevel: 'yellow',
  riskSummary: '整体创意方向获得认可，但存在PvP平衡性风险和无障碍设计缺失问题，建议在进入开发前解决关键问题。',
  stanceDistribution: [
    { stance: 'advocate', count: 2 },
    { stance: 'neutral', count: 1 },
    { stance: 'skeptic', count: 2 },
    { stance: 'blocker', count: 0 },
  ],
  priorityIssues: [
    { id: 'i1', title: 'PvP平衡性机制不明确', severity: 'high', description: '核心竞技玩法的数值平衡方案未详细说明，可能导致付费获胜争议。', evidence: ['铁血战士指出数值体系缺乏透明度', '数据分析师发现关键参数缺失'], affectedPersonas: ['铁血战士', '数据分析师'] },
    { id: 'i2', title: '无障碍功能完全缺失', severity: 'critical', description: '概念文档中未提及任何无障碍设计考虑，包括色盲支持、字幕选项和辅助模式。', evidence: ['无障碍先锋发现文档零提及', '家庭守护者表达担忧'], affectedPersonas: ['无障碍先锋', '家庭守护者'] },
    { id: 'i3', title: '叙事深度不足以支撑长线体验', severity: 'medium', description: '故事线较为线性，缺少分支叙事和角色深度发展。', evidence: ['故事猎人认为叙事框架单薄'], affectedPersonas: ['故事猎人'] },
    { id: 'i4', title: '新手引导设计薄弱', severity: 'low', description: '缺少详细的新手引导方案，可能导致休闲玩家流失。', evidence: ['家庭守护者指出操作门槛高'], affectedPersonas: ['家庭守护者', '白嫖达人'] },
  ],
  personaPerspectives: [
    { personaId: 'p1', personaName: '铁血战士', archetype: '硬核竞技者', stance: 'skeptic', confidence: 0.78, quote: '竞技系统看起来有潜力，但数值平衡是定时炸弹，不解决的话上线就是灾难。', keyEvidence: ['PvP数值框架缺失', '匹配机制未定义'] },
    { personaId: 'p2', personaName: '探索者', archetype: '世界漫游者', stance: 'advocate', confidence: 0.85, quote: '开放世界的设计理念很棒，探索奖励循环设计得很巧妙，让我很期待。', keyEvidence: ['探索奖励系统完善', '地图设计有层次'] },
    { personaId: 'p8', personaName: '故事猎人', archetype: '叙事爱好者', stance: 'neutral', confidence: 0.72, quote: '世界观设定有趣，但叙事方式太传统了，需要更多创新。', keyEvidence: ['叙事框架偏线性', '角色背景单薄'] },
    { personaId: 'p10', personaName: '独立鉴赏家', archetype: '创意追求者', stance: 'advocate', confidence: 0.91, quote: '这个创意方向太独特了！正是市场需要的新鲜血液。', keyEvidence: ['核心玩法创新', '艺术风格独特'] },
    { personaId: 'p5', personaName: '无障碍先锋', archetype: '包容性倡导者', stance: 'skeptic', confidence: 0.68, quote: '完全不考虑无障碍设计，这是在主动排斥大量潜在玩家。', keyEvidence: ['文档零无障碍提及', 'UI设计未考虑色盲'] },
  ],
  informationGaps: [
    'PvP匹配算法的具体实现方案',
    '无障碍设计的详细规划',
    '付费模式对游戏平衡的影响评估',
    '跨平台体验的一致性保证',
  ],
  calibration: { consistency: 0.82, coverage: 0.75, hallucination: 0.08 },
}

export const MOCK_REVIEWS: Review[] = [
  {
    id: 'rev-001',
    task_type: 'concept',
    target_title: '《星际漂流》概念设计文档',
    artifact_bundle: { title: '《星际漂流》概念设计文档', content: '...' },
    persona_pack: 'game-core',
    selected_personas: ['p1', 'p2', 'p8', 'p10', 'p5'],
    mode: 'standard',
    status: 'completed',
    created_at: '2026-05-20T10:30:00Z',
    completed_at: '2026-05-20T10:35:00Z',
    total_cost_usd: 0.42,
    report_json: MOCK_REPORT,
    report_markdown: null,
    calibration: { consistency: 0.82, coverage: 0.75, hallucination: 0.08 },
    persona_outputs: [
      { id: 'po-1', review_id: 'rev-001', persona_id: 'p1', persona_name: '铁血战士', status: 'completed', output_json: null, validation_result: null, cost_usd: 0.08, started_at: '2026-05-20T10:30:01Z', completed_at: '2026-05-20T10:31:00Z' },
      { id: 'po-2', review_id: 'rev-001', persona_id: 'p2', persona_name: '探索者', status: 'completed', output_json: null, validation_result: null, cost_usd: 0.09, started_at: '2026-05-20T10:30:02Z', completed_at: '2026-05-20T10:31:30Z' },
      { id: 'po-3', review_id: 'rev-001', persona_id: 'p8', persona_name: '故事猎人', status: 'completed', output_json: null, validation_result: null, cost_usd: 0.08, started_at: '2026-05-20T10:30:03Z', completed_at: '2026-05-20T10:32:00Z' },
      { id: 'po-4', review_id: 'rev-001', persona_id: 'p10', persona_name: '独立鉴赏家', status: 'completed', output_json: null, validation_result: null, cost_usd: 0.09, started_at: '2026-05-20T10:30:04Z', completed_at: '2026-05-20T10:32:30Z' },
      { id: 'po-5', review_id: 'rev-001', persona_id: 'p5', persona_name: '无障碍先锋', status: 'completed', output_json: null, validation_result: null, cost_usd: 0.08, started_at: '2026-05-20T10:30:05Z', completed_at: '2026-05-20T10:33:00Z' },
    ],
  },
  {
    id: 'rev-002',
    task_type: 'mechanic',
    target_title: '《暗影回廊》战斗系统设计',
    artifact_bundle: { title: '《暗影回廊》战斗系统设计', content: '...' },
    persona_pack: 'game-core',
    selected_personas: ['p1', 'p7', 'p11', 'p3', 'p6'],
    mode: 'full',
    status: 'running',
    created_at: '2026-05-21T08:00:00Z',
    completed_at: null,
    total_cost_usd: 0.18,
    report_json: null,
    report_markdown: null,
    calibration: null,
    persona_outputs: [
      { id: 'po-6', review_id: 'rev-002', persona_id: 'p1', persona_name: '铁血战士', status: 'completed', output_json: null, validation_result: null, cost_usd: 0.08, started_at: '2026-05-21T08:00:01Z', completed_at: '2026-05-21T08:01:00Z' },
      { id: 'po-7', review_id: 'rev-002', persona_id: 'p7', persona_name: '数据分析师', status: 'running', output_json: null, validation_result: null, cost_usd: 0.05, started_at: '2026-05-21T08:01:01Z', completed_at: null },
      { id: 'po-8', review_id: 'rev-002', persona_id: 'p11', persona_name: '速通猎手', status: 'running', output_json: null, validation_result: null, cost_usd: 0.05, started_at: '2026-05-21T08:01:02Z', completed_at: null },
      { id: 'po-9', review_id: 'rev-002', persona_id: 'p3', persona_name: '社交蝴蝶', status: 'pending', output_json: null, validation_result: null, cost_usd: 0, started_at: null, completed_at: null },
      { id: 'po-10', review_id: 'rev-002', persona_id: 'p6', persona_name: 'VR信徒', status: 'pending', output_json: null, validation_result: null, cost_usd: 0, started_at: null, completed_at: null },
    ],
  },
  {
    id: 'rev-003',
    task_type: 'ux',
    target_title: '《云端花园》界面原型',
    artifact_bundle: { title: '《云端花园》界面原型', content: '...' },
    selected_personas: ['p3', 'p4', 'p5'],
    mode: 'quick',
    status: 'pending',
    created_at: '2026-05-21T09:15:00Z',
    completed_at: null,
    total_cost_usd: 0,
    report_json: null,
    report_markdown: null,
    calibration: null,
    persona_outputs: [
      { id: 'po-11', review_id: 'rev-003', persona_id: 'p3', persona_name: '社交蝴蝶', status: 'pending', output_json: null, validation_result: null, cost_usd: 0, started_at: null, completed_at: null },
      { id: 'po-12', review_id: 'rev-003', persona_id: 'p4', persona_name: '白嫖达人', status: 'pending', output_json: null, validation_result: null, cost_usd: 0, started_at: null, completed_at: null },
      { id: 'po-13', review_id: 'rev-003', persona_id: 'p5', persona_name: '无障碍先锋', status: 'pending', output_json: null, validation_result: null, cost_usd: 0, started_at: null, completed_at: null },
    ],
  },
]

// persona_count 已从本类型中移除。它曾经写死为 6/8/5/10 并直接显示给用户，
// 而 persona_generate 标的 10 超过了所有评审模式的人数上限 8（见下方 REVIEW_MODES），
// 也就是一个可以被当场证伪的数。真正决定人数的是评审模式的 persona_count_range，
// 与技能无关，所以这里根本没有正确值可填——删掉字段而不是改个"对一点"的数，
// 才能保证它不会被谁顺手加回来。
export const SKILLS: { type: SkillType; name: string; description_zh: string; icon: string; task_types: string[]; use_cases: string[]; color: string; bg: string; border: string }[] = [
  {
    type: 'synthetic_playtest',
    name: '合成试玩',
    description_zh: '模拟真实玩家试玩体验，从上手到深度体验全流程评估，发现设计盲点与体验断裂',
    icon: '/skills/skill-game.png',
    task_types: ['concept_review', 'demo_first_play', 'devlog_review', 'update_announcement_review'],
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
    task_types: ['steam_page_review', 'kickstarter_review', 'product_feedback_review', 'pricing_page_review', 'onboarding_review'],
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
    task_types: ['monetization_review', 'discord_community_review', 'localization_review', 'update_announcement_review'],
    use_cases: ['付费模型压力测试', '社区危机预演', '本地化文化风险', '公关危机模拟'],
    color: 'text-brand-primary',
    bg: 'bg-brand-primary/10',
    border: 'border-brand-primary/30',
  },
  {
    type: 'persona_generate',
    name: '人格生成',
    description_zh: '根据产品特征自动生成定制化人格，创建专属评审角色，覆盖特殊用户群体',
    icon: '/skills/skill-persona.png',
    task_types: ['concept_review', 'demo_first_play', 'steam_page_review', 'kickstarter_review', 'discord_community_review'],
    use_cases: ['特定人群定制', '边缘用户覆盖', '跨文化人格', '特殊需求用户'],
    color: 'text-brand-primary',
    bg: 'bg-brand-primary/10',
    border: 'border-brand-primary/30',
  },
]

export const EVALUATION_DIMENSIONS: { id: string; name: string; description: string }[] = [
  { id: 'coverage', name: '覆盖度', description: '评审是否覆盖了所有关键维度和用户群体' },
  { id: 'depth', name: '深度', description: '评审洞察是否深入到根本原因而非停留在表面' },
  { id: 'consistency', name: '一致性', description: '不同角色间的评审结论是否逻辑自洽' },
  { id: 'actionability', name: '可行动性', description: '评审建议是否具体、可执行、可验证' },
  { id: 'evidence_quality', name: '证据质量', description: '评审结论是否有充分的证据链支撑' },
  { id: 'bias_detection', name: '偏见检测', description: '是否识别并标注了评审中的潜在偏见' },
  { id: 'novelty', name: '新颖性', description: '是否发现了常规评审容易忽略的盲点' },
  { id: 'ethical_safety', name: '伦理安全', description: '评审内容是否符合伦理标准，无歧视性输出' },
]
