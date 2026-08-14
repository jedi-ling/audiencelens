/**
 * 评审报告页 —— 渲染真实评审引擎（src/runner/aggregator.py）的原始输出。
 *
 * 字段契约以 aggregate_report() 的返回体为准（snake_case：executive_summary /
 * priority_fixes / persona_notes / major_disagreements / information_gaps /
 * compliance…），不是 mock-data.ts 里那套演示用的虚构 schema——历史上这页
 * 曾经按 mock 结构（riskLevel/priorityIssues/stanceDistribution）做盲转型，
 * 真实报告一进来就整页崩，这里是修复后的版本。
 *
 * 登录态分级：匿名用户拿到的 report_json 带 is_gated=true（后端
 * report_gating.py 裁剪过），走 GatedReportTeaser 分支。
 *
 * 两条硬性要求写在 ETHICS.md 里（"每份 AudienceLens 报告必须"）：
 *   1. Synthetic Banner，不得删除或弱化
 *   2. Limitations & Caveats 章节
 * 此前只有下载的 .md 带 banner（src/templates/report-template.md），网页端——
 * 也就是绝大多数人实际阅读报告的地方——一个字都没有。见 SyntheticBanner /
 * LimitationsSection，两个分支（完整报告 + 体验版）都必须渲染。
 */

import { useParams, Link } from 'react-router'
import { useState, useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { fetchReview, fetchReport, fetchReviewResult, fetchEvaluation, fetchEthicsReport, runEvaluation } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ApiError, api, claimPendingReviews, getToken, rememberPendingReview } from '@/lib/apiClient'
import type {
  Review,
  ReviewMode,
  EvaluationScorecard,
  EthicsReportView,
  Severity,
  CrossExamView,
  CrossExamArgument,
  CrossExamMode,
  CrossExamVoteChange,
  Persona,
} from '@/lib/mock-data'
import {
  EVALUATION_DIMENSIONS,
  ETHICS_SEVERITY_BADGE_CLASSES,
  REBUTTAL_STATUS_CLASSES,
  stereotypeRiskBadgeClass,
  toCrossExamView,
  toEthicsReportView,
} from '@/lib/mock-data'
import type { EthicsSeverity, RebuttalStatus, StereotypeRisk } from '@/lib/mock-data'
import { t, Trans, missingMarker } from '@/i18n/runtime'
import { getLocale } from '@/i18n/locale'
import { useDocumentTitle } from '@/i18n/head'
import { formatNumber, formatPercent, formatUsd } from '@/i18n/format'
import { tApiError, tApiErrorParts } from '@/i18n/api-error'
import { localizePersona } from '@/i18n/catalog'
import { usePersonaStore } from '@/store/persona-store'
import type { PlainMessageKey } from '@/i18n/keys.gen'
import SeverityBadge from '@/components/SeverityBadge'
import CalibrationGauge from '@/components/CalibrationGauge'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import { ArrowLeft, ChevronDown, ChevronUp, AlertTriangle, Loader2, File, FileText, Globe, Shield, FlaskConical, AlertOctagon, Lock, Users, HelpCircle, Scale, Zap, ListChecks, Microscope, CheckCircle2, XCircle, Bot, Info, Swords, MessageSquareQuote, ArrowRightLeft, MinusCircle, TrendingUp, TrendingDown, Minus, RefreshCw, Share2, Copy, Target, Layers } from 'lucide-react'

// ---------- 真实报告 schema（aggregator.py 输出的镜像；字段全部可选，缺了不崩） ----------

interface RealPriorityFix {
  priority?: number
  issue?: string
  severity?: string
  why_it_matters?: string
  affected_personas?: string[]
  suggested_fix?: string
  score?: number
}

interface RealPersonaNote {
  persona_id: string
  persona_name?: string
  stance?: string
  /** 兼容：部分旧数据/测试数据用 primary_stance 字段名 */
  primary_stance?: string
  evidence_top3?: string[]
  top_issues?: string[]
  continue_triggers?: string[]
  quit_triggers?: string[]
}

interface RealDisagreement {
  topic?: string
  persona_stances?: Array<{ persona_id?: string; stance?: string; evidence?: string }>
  resolution_suggestion?: string
}

/** 部分人格没跑成时引擎/后端写进报告的降级标记。
 *  两条链路（src/runner/cli.py 与 web 后端 services/__init__.py）字段同构，前端只需一套读法。 */
interface RealDegradation {
  degraded?: boolean
  attempted_count?: number
  succeeded_count?: number
  failed_count?: number
  failed_personas?: Array<{ persona_id?: string; persona_name?: string; error?: string }>
  notice?: string
}

/** 预算刹车（src/runner/cli.py 写进 report["budget"]）。
 *  人格并发跑到一半刹不住车，但交叉质询是之后才发起的额外付费调用——超预算就跳过。
 *  跳过之后「交叉质询」整节从页面上消失，页面上没有任何差别可看：
 *  用户会理解成"这次没什么争议"，真相是"钱到顶了，辩论根本没跑"。 */
interface RealBudget {
  max_cost_per_run_usd?: number
  persona_cost_usd?: number
  exceeded?: boolean
  skipped_stages?: string[]
  notice?: string
}

/** 三层校验的门控结果（src/runner/cli.py 写进 report["validation"]）。
 *  gated_out 里是"跑出来了但没过校验、因此不计入结论"的人格。
 *  不渲染的话，用户只会觉得"我选了 8 个人怎么只出来 5 个"。 */
interface RealValidation {
  gated_out?: Array<{ persona_id?: string; failure_reason?: string }>
}

/** 显式点名人格的匹配结果（src/runner/cli.py 只在用户点名了人格时写这个键）。
 *  notice 里是"你点名的角色有 N 个没参与"这类事实，不渲染的话用户会以为
 *  自己点的人全都上场了。 */
interface RealPanelSelection {
  requested?: string[]
  matched?: string[]
  missing?: string[]
  fell_back_to_auto?: boolean
  notice?: string
}

/** 共识判定的明细（aggregator.compute_consensus 的 shared_concerns）：
 *  谁提的、几人提的、合并了哪些措辞。给出来是让读者自己核对
 *  "这几条真是同一件事吗"，而不是只看一个光秃秃的计数。 */
interface RealSharedConcern {
  issue?: string
  personas?: string[]
  persona_count?: number
  is_consensus?: boolean
  title_variants?: string[]
}

export interface RealReport {
  /** 评审失败时 report_json 就是 {"error": ...}（v1 对外契约，见后端
   *  api/__init__.py::_report_json_for 与 services/report_gating.py：这个键被
   *  明确列为"不许裁掉的诚实声明"）。前端此前根本没读它——{"error":...} 是真值，
   *  于是一份全员失败的评审照样走完整报告分支。 */
  error?: unknown
  meta?: {
    task_type?: string
    target?: string
    generated_at?: string
    is_synthetic?: boolean
    /** 引擎侧写入的逐条注意事项（目前只有模拟占位输出会带），有就照原样展示 */
    caveats?: string[]
    /** 本次评审**产出物**的语言（BCP-47）。aggregator 按"取得到真值才写这个键"
     *  的规矩写入，所以缺这个键 = 语言未记录，**不等于中文**（契约 D7 / 8.4）。
     *  它与界面语言（ui_lang）是两件事，切界面语言不会改它。 */
    language?: string
  } | null
  executive_summary?: { primary_recommendation?: string; release_risk?: string; evidence_quality?: string } | null
  consensus?: {
    agreed_points?: string[]
    questioned_points?: string[]
    shared_concerns?: RealSharedConcern[]
    persona_count?: number
    threshold?: number
    min_personas_for_agreement?: number
  } | null
  major_disagreements?: RealDisagreement[]
  priority_fixes?: RealPriorityFix[]
  persona_notes?: RealPersonaNote[]
  information_gaps?: string[]
  next_human_test?: {
    suggested_tasks?: string[]
    /** 引擎给的是本次面板的真实受众特征串（"25-32 · 中国华东 · 核心 · PC/Switch"），
     *  不是人格名，也不是引擎推断的招募建议——标题文案必须按这个口径写 */
    recruit_types?: string[]
    recruit_types_basis?: string
    next_materials?: string[]
  } | null
  /** 库里同时存在三代形状（新 dict / 老 dict / 老 v1 的原始数组），所以保持
   *  unknown，一律经 toCrossExamView() 运行时收敛，不在类型层面撒谎。 */
  cross_examination?: unknown
  compliance?: { status?: string; ethics_score?: number; recommended_steps?: string[] } | null
  simulation_notice?: string | null
  degradation?: RealDegradation | null
  budget?: RealBudget | null
  validation?: RealValidation | null
  panel_selection?: RealPanelSelection | null
  /** 可证伪预测：把"建议"升格成带目标指标/对照方式/验证窗口的假设。
   *  引擎刻意不编效果量（confidence_basis 恒为合成面板启发式），
   *  展示时必须把这个口径一起写出来，否则用户会把它当成实测结论。 */
  predictions?: RealPrediction[]
  /** 自适应面板的执行轨迹。requested/enabled 分开是有意的：
   *  用户点名了角色时会被禁用，那种情况要说明"为什么没自适应"而不是装作没请求过。 */
  adaptive_panel?: RealAdaptivePanel | null
  is_gated?: boolean
  gated_counts?: { priority_fixes_hidden?: number; persona_notes_hidden?: number }
}

export interface RealPrediction {
  prediction_id?: string
  claim?: string
  issue?: string
  intervention?: string
  target_metric?: string
  direction?: 'increase' | 'decrease'
  success_criterion?: string
  verification_window?: string
  verification_method?: string
  severity?: string | null
  /** 0–1。它是启发式，不是实测命中率——渲染时永远和 confidence_basis 一起出现 */
  confidence?: number
  confidence_basis?: string
  status?: string
  is_synthetic?: boolean
  affected_personas?: string[]
}

export interface RealAdaptivePanel {
  requested?: boolean
  enabled?: boolean
  /** 请求了但被禁用时的原因，如 explicit_persona_selection */
  disabled_reason?: string | null
  method?: string
  initial_size?: number | null
  eligible_personas?: number
  executed_personas?: number
  /** 省下的人格调用次数。这是自适应面板唯一能自证价值的数字 */
  saved_persona_calls?: number
  min_score?: number | null
  decisions?: Array<{
    panel_size_before?: number
    recommended_persona_id?: string | null
    should_continue?: boolean
    stop_reason?: string | null
    score?: number
    unresolved_evidence?: string[]
  }>
  limitation?: string | null
}

interface RealCalibration {
  role_consistency?: { average?: number } | null
  coverage?: { average_distance?: number } | null
  hallucination?: { average?: number } | null
  overall_pass?: boolean
}

// ---------- 展示映射 ----------

/**
 * 展示映射一律**存 key 不存文案**（契约 3.4 例 7 / Layout.tsx 的样板）。
 *
 * 这些常量在模块求值时就固定了：存翻译结果的话，切换语言不会重新求值，
 * 风险徽标会一直停在打开页面时的那种语言。文案在渲染处才 t()。
 * color / bg / border 留在这里——样式不是文案，不进 key 表。
 */
const RISK_CONFIG: Record<string, { labelKey: PlainMessageKey; color: string; bg: string; border: string }> = {
  low: { labelKey: 'enum.release_risk.low', color: 'text-brand-primary', bg: 'bg-brand-primary/10', border: 'border-brand-primary/30' },
  medium: { labelKey: 'enum.release_risk.medium', color: 'text-severity-medium', bg: 'bg-severity-medium/10', border: 'border-severity-medium/30' },
  high: { labelKey: 'enum.release_risk.high', color: 'text-warm-orange', bg: 'bg-warm-orange/10', border: 'border-warm-orange/30' },
  critical: { labelKey: 'enum.release_risk.critical', color: 'text-severity-critical', bg: 'bg-severity-critical/10', border: 'border-severity-critical/30' },
}

/** release_risk 缺失/取值不认识时的显示。以前这里是 `?? RISK_CONFIG.medium`：
 *  报告里根本没有 executive_summary，页面照样打出"发布风险评估：中风险"——
 *  一个纯属编造的等级，而用户会拿它做发布决策。缺就显示「—」并说明缺了什么。 */
const UNKNOWN_RISK = { color: 'text-text-muted', bg: 'bg-bg-card', border: 'border-border' }

/**
 * 「这里没有值」的统一显示符号。
 *
 * **刻意不进 key 表**：它是排版符号不是文案，中英两侧写法完全相同（U+2014），
 * 抽成 key 只会得到一条 zh 与 en 逐字相同的条目，外加 15 处运行时查表。
 * i18n:scan 会报它——那是因为扫描器的 CJK 字符类把中文标点也算进去了，
 * 不是漏外化。同理还有下面拼阶段标识用的 ' · '。
 */
const DASH = '—'

const EVIDENCE_QUALITY_KEYS: Record<string, PlainMessageKey> = {
  strong: 'enum.evidence_quality.strong',
  medium: 'enum.evidence_quality.medium',
  weak: 'enum.evidence_quality.weak',
  insufficient: 'enum.evidence_quality.insufficient',
}

/**
 * 证据充分度的显示值。
 *
 * 三条分支刻意分开：认识的档位出译文；不认识的档位**明说不认识并附上原值**
 * （不把后端英文键当标签直出——那正是契约 D8 点名的反例）；根本没给就是「—」。
 */
function evidenceQualityLabel(raw?: string): string {
  if (!raw) return DASH
  const key = EVIDENCE_QUALITY_KEYS[raw]
  return key ? t(key) : t('page.report.unknown_level.value', { raw })
}

// 立场是各任务类型自己的枚举（"加愿望单"/"值得推进"/"观望"…），无法穷举——按出现顺序配色
const STANCE_PALETTE = ['#0071e3', '#ff9f0a', '#ff6b35', '#ff3355', '#32ade6', '#a78bfa']

const MODE_BADGE: Record<ReviewMode, { labelKey: PlainMessageKey; color: string; bg: string; Icon: typeof Zap }> = {
  quick: { labelKey: 'enum.mode_badge.quick', color: 'text-cyan', bg: 'bg-cyan/10', Icon: Zap },
  standard: { labelKey: 'enum.mode_badge.standard', color: 'text-brand-primary', bg: 'bg-brand-primary/10', Icon: ListChecks },
  full: { labelKey: 'enum.mode_badge.full', color: 'text-warm-orange', bg: 'bg-warm-orange/10', Icon: Microscope },
}

/** 交叉质询三档模式的 label / desc。原来读 mock-data 的 CROSS_EXAM_MODE_LABELS，
 *  那两份常量是 zh 事实源，这里换成它们的 i18n 出口，措辞逐字一致。 */
const CROSS_EXAM_MODE_LABEL_KEYS: Record<CrossExamMode, PlainMessageKey> = {
  derived_summary: 'enum.cross_exam_mode.derived_summary.label',
  moderated_rebuttal: 'enum.cross_exam_mode.moderated_rebuttal.label',
  multi_agent_rebuttal: 'enum.cross_exam_mode.multi_agent_rebuttal.label',
}

const CROSS_EXAM_MODE_DESC_KEYS: Record<CrossExamMode, PlainMessageKey> = {
  derived_summary: 'enum.cross_exam_mode.derived_summary.desc',
  moderated_rebuttal: 'enum.cross_exam_mode.moderated_rebuttal.desc',
  multi_agent_rebuttal: 'enum.cross_exam_mode.multi_agent_rebuttal.desc',
}

const REBUTTAL_STATUS_KEYS: Record<RebuttalStatus, PlainMessageKey> = {
  ok: 'enum.rebuttal_status.ok',
  partial: 'enum.rebuttal_status.partial',
  failed: 'enum.rebuttal_status.failed',
  skipped: 'enum.rebuttal_status.skipped',
}

const ETHICS_SEVERITY_KEYS: Record<EthicsSeverity, PlainMessageKey> = {
  high: 'enum.ethics_severity.high',
  medium: 'enum.ethics_severity.medium',
  low: 'enum.ethics_severity.low',
}

const STEREOTYPE_RISK_KEYS: Record<StereotypeRisk, PlainMessageKey> = {
  low: 'enum.stereotype_risk.low',
  medium: 'enum.stereotype_risk.medium',
  high: 'enum.stereotype_risk.high',
}

/** null 走 unknown 那一档：「没测出来」和「低风险」是两回事，不许合并。
 *  原来读 mock-data 的 stereotypeRiskLabel()，它只出中文。 */
function stereotypeRiskText(risk: StereotypeRisk | null): string {
  return t(risk === null ? 'enum.stereotype_risk.unknown' : STEREOTYPE_RISK_KEYS[risk])
}

const VALID_SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']

/** 评估记分卡的单维度满分。后端 evaluation_service.py 每个维度只产出 {0,1,2,3}，
 *  passed = score >= 2；只有 scorecard.overall_score 是 0–100。
 *  柱状图 Y 轴此前写死 0–100，于是满分 3 分的柱子恒定贴着地面，
 *  整块看起来像"每个维度都接近零分"。 */
const DIMENSION_MAX_SCORE = 3

/** 维度 id 不在本地词表里时明说不认识，不把 snake_case 当正常标题直出 */
function dimensionLabel(id: string, name?: string): string {
  return name ?? t('page.report.evaluation_dimension.value', { id })
}

/** 立场是引擎的枚举原词（wire key），**永不翻译**；只有"两个字段都没给"
 *  这种前端自造的分组名才走 key 表。 */
function noteStance(note: RealPersonaNote): string {
  return note.stance ?? note.primary_stance ?? t('page.report.stance.value')
}

/**
 * 报告字段里的人格展示名（persona_notes 等）。
 *
 * 报告 JSON 里的 `persona_name` 就是后端 `persona_outputs.persona_name`——10.3 红线
 * 钉死那个字段永远读 `name`，恒中文，这里**不改**它的事实源。这个函数只管
 * "拿这个 persona_id 去当前人格库里找到人，换一张给屏幕看的脸"：
 *   · 中文界面：报告自带的 persona_name 本来就是中文，直接用，不用查库。
 *   · 英文界面：人格库里能找到 → 走 localizePersona 取 display_name_en
 *     （缺 overlay 会被 localizePersona 自己标成 ⟦missing:…⟧，同一条规则）；
 *     找不到（目录漂移——比如历史报告引用的人格已经从包里下线，人格库里
 *     压根没有这一条）→ 同样显式标记，不回落成报告里的中文 persona_name，
 *     那正是 D8 点名禁止的"英文界面里混中文且没人发现"。
 */
function personaDisplayName(personas: Persona[], id: string | undefined, fallbackName: string | undefined): string {
  // fallbackName ?? id：与调用点原来的 `note.persona_name ?? note.persona_id` 是
  // 同一个兜底顺序，只是从内联表达式挪进了这个函数，没有新造规则。
  if (getLocale() === 'zh') return fallbackName ?? id ?? ''
  const found = id ? personas.find((p) => p.id === id) : undefined
  if (found) return localizePersona(found).name
  console.error('[ReportPage] 报告引用的人格不在当前人格库里，无法取 display_name_en：', id)
  return missingMarker(`persona.${id ?? 'unknown'}.display_name`, getLocale())
}

// ---------- ETHICS.md 强制项：Synthetic Banner + Limitations & Caveats ----------

/**
 * 合成面板横幅。ETHICS.md：「每份 AudienceLens 报告必须包含 Synthetic Banner
 * （不得删除或弱化）」。措辞对齐 src/templates/report-template.md 顶部那段，
 * 不另起一套说法——两处口径不一致比没有更糟。
 *
 * 位置固定在页面最顶部（标题之上），用高对比警示色而非灰色小字：伦理指南里
 * "弱化"和"删除"是同一档问题，摆在需要滚动才看得到的地方就是弱化。
 */
export function SyntheticBanner() {
  return (
    <div className="mb-4 rounded-xl border-2 border-warm-orange bg-warm-orange/10 p-4">
      <div className="flex items-start gap-3">
        <Bot className="mt-0.5 h-5 w-5 shrink-0 text-warm-orange" strokeWidth={1.75} />
        <div>
          <p className="text-sm font-bold text-warm-orange md:text-base">
            {t('page.report.synthetic_banner.title')}
          </p>
          <p className="mt-1.5 text-sm text-text-primary">
            {t('page.report.synthetic_banner.desc')}
          </p>
        </div>
      </div>
    </div>
  )
}

/**
 * 降级横幅：本次有人格没跑成，结论只据剩下的几位得出。
 * 不显式渲染的话，一份"8 位挂 6 位"的报告在页面上和满编报告长得一模一样。
 */
function DegradationNotice({ degradation }: { degradation?: RealDegradation | null }) {
  if (!degradation?.degraded) return null
  const failed = degradation.failed_personas ?? []
  // notice 是引擎/后端写的自由文本（产出物），有就原样透出，一个字不翻。
  // 没有才用前端这句——succeeded_count 缺失时换一条不带数字的措辞，
  // 不写"0 位"也不写"部分 位"：前者是编造，后者是原来那句拼出来的病句。
  const notice =
    degradation.notice?.trim() ||
    (typeof degradation.succeeded_count === 'number'
      ? t('page.report.degradation.desc', {
          count: degradation.failed_count ?? failed.length,
          succeeded: degradation.succeeded_count,
        })
      : t('page.report.degradation_partial.desc', { count: degradation.failed_count ?? failed.length }))
  const failedLabels = failed.map((p) => p.persona_name || p.persona_id).filter(Boolean)
  return (
    <div className="mb-4 rounded-xl border-2 border-severity-critical bg-severity-critical/10 p-4">
      <div className="flex items-start gap-3">
        <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-severity-critical" strokeWidth={1.75} />
        <div>
          <p className="text-sm font-bold text-severity-critical md:text-base">{notice}</p>
          {failedLabels.length > 0 && (
            <p className="mt-1.5 text-sm text-text-primary">
              {t('page.report.degradation.label', { names: failedLabels.join(t('page.report.sep_enum')) })}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * 高级技能/红队被静默降级的提醒。
 *
 * 功能完整性审查 P1：review.skill_degraded 这个字段一直存在（免费次数用完时
 * 后端会把红队/高级技能降级，AskPage 创建评审那一刻会弹一次提示），但报告页
 * 从没读过它——用户如果不是当场看到那句提示、而是过后从历史记录点进报告，
 * 就永远不知道这次评审其实没跑红队/高级技能，会把"没跑出争议点"误读成
 * "评审出来就是没什么好争的"。这里补上报告页的持久化展示。
 */
function SkillDegradedNotice({ notice }: { notice?: string | null }) {
  if (!notice) return null
  return (
    <div className="mb-4 rounded-xl border-2 border-warm-orange bg-warm-orange/10 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warm-orange" strokeWidth={1.75} />
        <p className="text-sm font-bold text-warm-orange md:text-base">{notice}</p>
      </div>
    </div>
  )
}

/** 校验门控：这些人格跑出来了，但输出没过 schema / 角色一致性 / 证据核对，
 *  所以**不计入**下面任何结论。引擎只回传英文的失败类型枚举
 *  （src/runner/cli.py 的 RETRY_SCHEMA / RETRY_ROLE_DRIFT / RETRY_HALLUCINATION），
 *  这里逐条翻译；认不出的枚举原样显示，不猜、也不吞。 */
const GATE_REASON_KEYS: Record<string, PlainMessageKey> = {
  schema_failure: 'enum.gate_reason.schema_failure',
  role_drift: 'enum.gate_reason.role_drift',
  hallucination: 'enum.gate_reason.hallucination',
}

/** 三分支：认得的枚举出译文；认不出的**明说不认识并附原值**；引擎压根没回传就说没回传。 */
function gateReasonLabel(raw?: string): string {
  if (!raw) return t('page.report.gate.empty')
  const key = GATE_REASON_KEYS[raw]
  return key ? t(key) : t('page.report.gate.label', { raw })
}

function ValidationGateNotice({ validation }: { validation?: RealValidation | null }) {
  const gatedOut = (validation?.gated_out ?? []).filter((g) => g.persona_id)
  if (gatedOut.length === 0) return null
  return (
    <div className="mb-4 rounded-xl border border-warm-orange/50 bg-warm-orange/5 p-4">
      <div className="flex items-start gap-3">
        <Shield className="mt-0.5 h-5 w-5 shrink-0 text-warm-orange" strokeWidth={1.75} />
        <div className="min-w-0">
          <p className="text-sm font-bold text-warm-orange">
            {t('page.report.gate.title', { count: gatedOut.length })}
          </p>
          <ul className="mt-2 space-y-1">
            {gatedOut.map((g, i) => (
              <li key={`${g.persona_id}-${i}`} className="text-sm text-text-primary">
                <span className="font-mono text-xs text-text-muted">{g.persona_id}</span>
                <span className="mx-1.5 text-text-muted">·</span>
                {gateReasonLabel(g.failure_reason)}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

/** 可证伪预测清单。
 *
 * 这是报告里唯一"能被真实世界证伪"的部分：每条都有目标指标、变更方向、
 * 判定标准和验证窗口。它存在的意义是让用户能回填真实结果（判断留档闭环），
 * 而不是又一份"建议清单"。
 *
 * 展示纪律：confidence 必须和 confidence_basis 同框出现。那个数字是合成面板的
 * 启发式权重，不是历史命中率——单独把 "0.72" 摆出来，用户会当成实测置信度，
 * 而这正是本仓库反复防的那类过度声称。
 */
function PredictionsSection({ predictions }: { predictions?: RealPrediction[] }) {
  const rows = (predictions ?? []).filter((p) => p && (p.claim || p.intervention))
  if (rows.length === 0) return null

  const DIRECTION_KEYS: Record<string, PlainMessageKey> = {
    increase: 'enum.direction.increase',
    decrease: 'enum.direction.decrease',
  }

  return (
    <div className="mb-6 rounded-xl border border-border bg-bg-card p-4 md:p-5">
      <div className="mb-1 flex items-center gap-2">
        <Target className="w-4 h-4 text-cyan" strokeWidth={1.25} />
        <h3 className="text-sm font-semibold text-text-primary">{t('page.report.predictions.title')}</h3>
        <span className="ml-auto text-xs text-text-muted">{t('page.report.predictions.badge', { count: rows.length })}</span>
      </div>
      <p className="mb-4 text-xs leading-relaxed text-text-muted">
        {t('page.report.predictions.desc')}
      </p>

      <ul className="space-y-3">
        {rows.map((p, i) => (
          <li key={p.prediction_id ?? i} className="rounded-lg border border-border bg-bg-secondary p-3">
            <p className="text-sm text-text-primary">{p.claim || p.intervention}</p>

            <dl className="mt-2 grid gap-x-4 gap-y-1.5 text-xs sm:grid-cols-2">
              {p.target_metric && (
                <div className="flex gap-1.5">
                  <dt className="shrink-0 text-text-muted">{t('page.report.prediction_metric.label')}</dt>
                  <dd className="text-text-secondary">
                    {p.target_metric}
                    {/* direction 不在枚举里就整块不渲染：括号里放一个后端原始码
                        对读者没有任何意义，而它旁边就是指标名，会被读成指标的一部分 */}
                    {p.direction && DIRECTION_KEYS[p.direction] && (
                      <span className="ml-1 text-cyan">
                        {t('page.report.prediction_metric.hint', { direction: t(DIRECTION_KEYS[p.direction]) })}
                      </span>
                    )}
                  </dd>
                </div>
              )}
              {p.verification_window && (
                <div className="flex gap-1.5">
                  <dt className="shrink-0 text-text-muted">{t('page.report.prediction_window.label')}</dt>
                  <dd className="text-text-secondary">{p.verification_window}</dd>
                </div>
              )}
              {p.success_criterion && (
                <div className="flex gap-1.5 sm:col-span-2">
                  <dt className="shrink-0 text-text-muted">{t('page.report.prediction_criterion.label')}</dt>
                  <dd className="text-text-secondary">{p.success_criterion}</dd>
                </div>
              )}
              {p.verification_method && (
                <div className="flex gap-1.5 sm:col-span-2">
                  <dt className="shrink-0 text-text-muted">{t('page.report.prediction_method.label')}</dt>
                  <dd className="text-text-secondary">{p.verification_method}</dd>
                </div>
              )}
            </dl>

            {typeof p.confidence === 'number' && (
              // 数字与口径同框：单独摆 0.72 会被读成实测置信度
              <p className="mt-2 border-t border-border pt-2 text-[11px] text-text-muted">
                <Trans
                  k="page.report.predictions.hint"
                  vars={{ pct: formatPercent(p.confidence) }}
                  slots={{ emph: (s) => <b className="font-medium">{s}</b> }}
                />
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** 自适应面板的执行轨迹。
 *
 * 这个区块回答一个用户会直接问的问题："你说帮我省了成本，省在哪？"
 * saved_persona_calls 是它唯一能自证价值的数字，所以放在最显眼的位置。
 *
 * requested 与 enabled 分开展示是有意的：用户点名了角色时会被自动禁用，
 * 那种情况必须说明"为什么没自适应"，而不是装作用户没请求过。
 */
function AdaptivePanelSection({ adaptive }: { adaptive?: RealAdaptivePanel | null }) {
  // 没请求过就整块不显示——固定面板是默认行为，没必要天天告诉用户"你没开这个功能"
  if (!adaptive?.requested) return null

  const DISABLED_REASON_KEYS: Record<string, PlainMessageKey> = {
    explicit_persona_selection: 'enum.disabled_reason.explicit_persona_selection',
  }
  const STOP_REASON_KEYS: Record<string, PlainMessageKey> = {
    cost_budget_reached: 'enum.stop_reason.cost_budget_reached',
    marginal_value_below_threshold: 'enum.stop_reason.marginal_value_below_threshold',
  }

  const saved = adaptive.saved_persona_calls ?? 0
  const disabledReasonKey = adaptive.disabled_reason ? DISABLED_REASON_KEYS[adaptive.disabled_reason] : undefined

  return (
    <div className="mb-6 rounded-xl border border-border bg-bg-card p-4 md:p-5">
      <div className="mb-3 flex items-center gap-2">
        <Layers className="w-4 h-4 text-brand-primary" strokeWidth={1.25} />
        <h3 className="text-sm font-semibold text-text-primary">{t('page.report.adaptive.title')}</h3>
      </div>

      {!adaptive.enabled ? (
        <p className="text-sm text-text-secondary">
          {t('page.report.adaptive.empty')}
          {adaptive.disabled_reason && (
            <span className="text-text-muted">
              {' '}
              {disabledReasonKey
                ? t(disabledReasonKey)
                : t('page.report.adaptive_reason.label', { raw: adaptive.disabled_reason })}
            </span>
          )}
        </p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-border bg-bg-secondary p-3">
              <p className="text-xs text-text-muted">{t('page.report.adaptive_executed.label')}</p>
              <p className="mt-1 font-display text-xl text-text-primary">
                {adaptive.executed_personas ?? DASH}
                <span className="text-sm text-text-muted"> / {adaptive.eligible_personas ?? DASH}</span>
              </p>
            </div>
            <div className="rounded-lg border border-border bg-bg-secondary p-3">
              <p className="text-xs text-text-muted">{t('page.report.adaptive_saved.label')}</p>
              <p className={cn('mt-1 font-display text-xl', saved > 0 ? 'text-brand-primary' : 'text-text-primary')}>
                {saved}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-bg-secondary p-3">
              <p className="text-xs text-text-muted">{t('page.report.adaptive_initial.label')}</p>
              <p className="mt-1 font-display text-xl text-text-primary">{adaptive.initial_size ?? DASH}</p>
            </div>
          </div>

          {(adaptive.decisions ?? []).length > 0 && (
            <ol className="mt-4 space-y-1.5">
              {(adaptive.decisions ?? []).map((d, i) => {
                const stopKey = STOP_REASON_KEYS[d.stop_reason ?? '']
                return (
                  <li key={i} className="flex items-start gap-2 text-xs text-text-secondary">
                    <span className="shrink-0 text-text-muted">
                      {t('page.report.adaptive_step.label', { count: d.panel_size_before ?? 0 })}
                    </span>
                    <span>
                      {d.should_continue
                        ? t('page.report.adaptive_step.value', {
                            persona: d.recommended_persona_id ?? t('page.report.adaptive_step.hint'),
                          })
                        : stopKey
                          ? t(stopKey)
                          : t('page.report.adaptive_stop.label')}
                    </span>
                  </li>
                )
              })}
            </ol>
          )}

          {adaptive.limitation && (
            // 引擎自带的局限声明，原样透出——这是"扩面分数是启发式而非实测信息增益"的自陈
            <p className="mt-3 border-t border-border pt-3 text-[11px] leading-relaxed text-text-muted">
              {t('page.report.adaptive.hint')}
            </p>
          )}
        </>
      )}
    </div>
  )
}

/** 显式点名人格的匹配结果提示。引擎只在用户点名了人格时写 panel_selection，
 *  有 notice（"你点名的角色有 N 个没参与"）就必须让用户不滚动也能看到——
 *  否则用户会把结论当成"我点的那几个人的意见"。missing 为空时 notice 也为空，
 *  这时不渲染，不给页面塞一条"一切正常"的废话。 */
function PanelSelectionNotice({ panelSelection }: { panelSelection?: RealPanelSelection | null }) {
  const notice = panelSelection?.notice?.trim()
  if (!notice) return null
  return (
    <div className="mb-4 rounded-xl border border-warm-orange/50 bg-warm-orange/5 p-4">
      <div className="flex items-start gap-3">
        <Info className="mt-0.5 h-5 w-5 shrink-0 text-warm-orange" strokeWidth={1.75} />
        <div className="min-w-0">
          <p className="text-sm font-bold text-warm-orange">{t('page.report.panel_selection.title')}</p>
          {/* notice 是引擎写进报告的事实陈述（产出物），原样透出，不翻译 */}
          <p className="mt-1.5 text-sm text-text-primary">{notice}</p>
          {(panelSelection?.matched ?? []).length > 0 && (
            <p className="mt-1.5 text-xs text-text-muted">
              {t('page.report.panel_selection.label', {
                names: (panelSelection?.matched ?? []).join(t('page.report.sep_enum')),
              })}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

/** 预算刹车提示。只在引擎明确写了 exceeded 时出现，数字全部取自 report.budget，
 *  没有 notice 就用两个真实金额自己组一句——不编造任何金额或"节省了多少"。 */
function BudgetNotice({ budget }: { budget?: RealBudget | null }) {
  if (!budget?.exceeded) return null
  const cap = budget.max_cost_per_run_usd
  const spent = budget.persona_cost_usd
  const fallback =
    typeof cap === 'number' && typeof spent === 'number'
      ? t('page.report.budget.desc', { spent: formatUsd(spent), cap: formatUsd(cap) })
      : t('page.report.budget_generic.desc')
  const stages = budget.skipped_stages ?? []
  return (
    <div className="mb-4 rounded-xl border-2 border-warm-orange bg-warm-orange/10 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warm-orange" strokeWidth={1.75} />
        <div className="min-w-0">
          <p className="text-sm font-bold text-warm-orange md:text-base">
            {t('page.report.budget.title')}
          </p>
          <p className="mt-1.5 text-sm text-text-primary">{budget.notice?.trim() || fallback}</p>
          {stages.includes('cross_examination') && (
            <p className="mt-1.5 text-sm text-text-primary">
              {t('page.report.budget.hint')}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * 报告里根本没有交叉质询区块时的说明。
 *
 * 以前这里什么都不渲染，整节凭空消失，页面上和"跑过辩论、大家没分歧"长得一模一样。
 * 缺席的原因引擎并没有逐条记进报告（可能是模式不含反驳环节、可能是没有真分歧、
 * 也可能是预算刹车），所以这里只在 budget.exceeded 时点名成本原因，其余情况
 * 如实说"报告没有记录原因"——猜一个具体理由和之前一声不吭同样是误导。
 */
function CrossExamAbsentNotice({ budget }: { budget?: RealBudget | null }) {
  const skippedForCost = budget?.exceeded === true && (budget.skipped_stages ?? []).includes('cross_examination')
  return (
    <div className="mb-6">
      <div className="mb-4 flex items-center gap-2">
        <Swords className="h-5 w-5 text-text-muted" strokeWidth={1.25} />
        <h3 className="text-lg font-semibold text-text-primary">{t('page.report.cross_exam.title')}</h3>
      </div>
      <div className="rounded-xl border border-border bg-bg-secondary/40 p-4 text-sm text-text-secondary md:p-5">
        {skippedForCost ? (
          <p>{t('page.report.cross_exam_skipped.desc')}</p>
        ) : (
          <p>{t('page.report.cross_exam_absent.desc')}</p>
        )}
      </div>
    </div>
  )
}

// ---------- 失败态：评审跑挂了 / 报告加载不出来 ----------

/**
 * 把 report_json.error 收敛成一句能给人看的原因。
 *
 * 后端写进来的通常是 error_message 字符串（api/__init__.py::_report_json_for），
 * 但老数据/别的链路可能塞 dict，所以非字符串一律 JSON 序列化后原样展示——
 * 宁可给一串难看的 JSON，也不能因为"形状不认识"就把失败原因吞掉。
 */
function failureDetail(raw: unknown): string | null {
  if (typeof raw === 'string') return raw.trim() || null
  if (raw === null || raw === undefined) return null
  try {
    return JSON.stringify(raw)
  } catch {
    return String(raw)
  }
}

/**
 * 判定"这份报告其实是一次失败的评审"。
 *
 * 两个信号任一成立即算失败：
 *   · review.status === 'failed'  —— 评审记录自己说的
 *   · report.error 非空           —— v1 契约：失败评审的 report_json 就是 {"error": ...}
 * 返回 null 表示不是失败；返回对象时 reason 可能为 null（失败了但没回传原因，
 * 这本身也要如实说，不能默默按成功渲染）。
 *
 * 历史病灶：空态判断只有 `if (!review || !report)`，而 {"error": ...} 是真值，
 * 于是失败评审直接落进完整报告分支——summary 为 undefined，风险等级被兜底成
 * "中风险"，共识/存疑点显示 0/0，看起来像"跑完了、没发现问题"。
 *
 * 功能完整性审查 P1：原来只读 report.error，漏了 review.error_message 这条
 * 后端专门开的兜底路径——引擎写了半份报告又失败时 report_json 非空、
 * report.error 读不到东西，这时唯一能看到失败原因的地方就是 error_message。
 * 两个都读不到才真的说明后端没回传原因，不能提前放弃。
 */
function reviewFailure(review: Review | null, report: RealReport | null): { reason: string | null } | null {
  const reason = failureDetail(report?.error) ?? failureDetail(review?.error_message)
  if (reason) return { reason }
  if (review?.status === 'failed') return { reason: null }
  return null
}

/** 评审失败：绝不渲染任何结论，只讲清楚"没有结论"和为什么。 */
function ReviewFailedNotice({
  reviewId,
  review,
  reason,
}: {
  reviewId?: string
  review: Review | null
  reason: string | null
}) {
  return (
    <div className="max-w-3xl mx-auto px-4 py-10 animate-fade-in">
      <div className="rounded-xl border-2 border-severity-critical bg-severity-critical/10 p-5 md:p-6">
        <div className="flex items-start gap-3">
          <AlertOctagon className="mt-0.5 h-6 w-6 shrink-0 text-severity-critical" strokeWidth={1.75} />
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-severity-critical md:text-xl">{t('page.report.failed.title')}</h1>
            <p className="mt-2 text-sm text-text-primary">
              {t('page.report.failed.desc')}
            </p>
            {review?.target_title && (
              <p className="mt-2 text-sm text-text-secondary">
                {t('page.report.failed.label', { title: review.target_title })}
              </p>
            )}
            <div className="mt-4 rounded-lg border border-severity-critical/40 bg-bg-card p-3">
              {/* 标题里就写明"后端原文"：下面那段可能是中文，而界面可能是英文。
                  与其把它翻错，不如如实标注它的出处，让读者知道自己在读什么。 */}
              <p className="text-xs text-text-muted">{t('page.report.failed.hint')}</p>
              {reason ? (
                <p className="mt-1 whitespace-pre-wrap break-words font-mono text-xs text-text-primary">{reason}</p>
              ) : (
                <p className="mt-1 text-xs text-text-primary">
                  {t('page.report.failed.empty')}
                </p>
              )}
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              {reviewId && (
                <Link
                  to={`/review/${reviewId}`}
                  className="rounded-lg border border-border bg-bg-card px-4 py-2 text-sm text-text-secondary hover:border-brand-primary/30 hover:text-brand-primary transition-all"
                >
                  {t('page.report.link_detail.cta')}
                </Link>
              )}
              <Link
                to="/review/new"
                className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors"
              >
                {t('page.report.link_new_review.cta')}
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * 报告加载失败（网络断了 / 403 / 500 / 后端没起来）。
 *
 * 以前这一档和"报告还没生成"共用一句"报告尚未生成"：用户看不出是自己等得不够久，
 * 还是请求根本没通，也没有任何重试入口。这两件事必须分开说。
 */
function ReportLoadError({ error, reviewId, onRetry }: { error: Error; reviewId?: string; onRetry: () => void }) {
  const status = error instanceof ApiError ? error.status : null
  const needLogin = error instanceof ApiError && (error.status === 401 || error.status === 403)
  // 后端 message 的语种可能与界面不一致：tApiErrorParts 把它拆成
  // 「界面语言的主文案」+「后端原文 detail」，detail 只进 title 属性，
  // 不与主文案并排显示——英文界面上并排一句中文，用户会以为界面坏了。
  const { text, detail } = tApiErrorParts(error, 'common.ui.unknown_error')
  return (
    <div className="max-w-3xl mx-auto px-4 py-10 animate-fade-in">
      <div className="rounded-xl border-2 border-warm-orange bg-warm-orange/10 p-5 md:p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-6 w-6 shrink-0 text-warm-orange" strokeWidth={1.75} />
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-warm-orange md:text-xl">{t('page.report.load_error.title')}</h1>
            <p className="mt-2 text-sm text-text-primary">
              {t('page.report.load_error.desc')}
            </p>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm text-text-secondary" title={detail}>
              {text}
              {status !== null && status > 0 && <span className="ml-1 font-mono text-xs text-text-muted">HTTP {status}</span>}
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                onClick={onRetry}
                className="flex items-center gap-2 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors"
              >
                <RefreshCw className="h-4 w-4" strokeWidth={1.5} />
                {t('common.action.retry')}
              </button>
              {needLogin && (
                <Link
                  to="/login"
                  className="rounded-lg border border-brand-primary/30 bg-bg-card px-4 py-2 text-sm text-brand-primary hover:bg-brand-primary/10 transition-colors"
                >
                  {t('page.report.link_login.cta')}
                </Link>
              )}
              {reviewId && (
                <Link
                  to={`/review/${reviewId}`}
                  className="rounded-lg border border-border bg-bg-card px-4 py-2 text-sm text-text-secondary hover:border-brand-primary/30 hover:text-brand-primary transition-all"
                >
                  {t('page.report.link_detail.cta')}
                </Link>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

/** 逐条来自 ETHICS.md（「偏见与局限性」「预筛工具，不是决策依据」「材料决定质量」），
 *  不新增任何该文档里没有的说法——两份材料必须能对得上。 */
/** 存 key 不存文案：模块级常量存翻译结果的话，切语言时不会重新求值，
 *  这五条会一直停在打开页面时的那种语言。渲染处才 t()。 */
const LIMITATION_KEYS: PlainMessageKey[] = [
  'page.report.limitation_synthetic',
  'page.report.limitation_variance',
  'page.report.limitation_materials',
  'page.report.limitation_demographic',
  'page.report.limitation_feedback_loop',
]

/** ETHICS.md 强制项之二：Limitations & Caveats 章节（下载的 .md 一直有，网页端此前没有）。 */
export function LimitationsSection({ caveats }: { caveats?: string[] }) {
  const extra = (caveats ?? []).filter((c) => typeof c === 'string' && c.trim())
  return (
    <section className="mb-6 rounded-xl border border-warm-orange/40 bg-bg-card p-4 md:p-5">
      <div className="mb-3 flex items-center gap-2">
        <Info className="h-5 w-5 text-warm-orange" strokeWidth={1.5} />
        <h3 className="text-base font-semibold text-text-primary">{t('page.report.limitations.title')}</h3>
      </div>
      <ul className="space-y-2">
        {/* caveats 是引擎写进 meta 的自由文本（产出物），原样在前；下面五条是
            ETHICS.md 的固定条款，走 key 表。两批合成一个列表渲染，顺序不变。 */}
        {[...extra, ...LIMITATION_KEYS.map((k) => t(k))].map((item, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-text-primary">
            <span className="mt-0.5 shrink-0 text-warm-orange">•</span>
            {item}
          </li>
        ))}
      </ul>
    </section>
  )
}

// ---------- 交叉质询 ----------

/** 三档模式的徽标配色。派生摘要**故意**用最暗的中性色：它是三档里最弱的一种，
 *  给它绿色徽标会让"没跑反驳"看起来像一项成就。 */
const CROSS_EXAM_MODE_BADGE: Record<CrossExamMode, string> = {
  derived_summary: 'bg-bg-secondary text-text-muted border-border',
  moderated_rebuttal: 'bg-cyan/10 text-cyan border-cyan/30',
  multi_agent_rebuttal: 'bg-brand-primary/10 text-brand-primary border-brand-primary/30',
}

/** 正反两方的准确叫法。引擎里 pro = 认为问题更严重的一方（A 系列），
 *  con = 认为更轻的一方（B 系列）——不是"支持/反对某个方案"，别简写成"支持方"。 */
const CROSS_EXAM_SIDE_META = {
  pro: { labelKey: 'page.report.argument_pro.label', color: 'text-warm-orange', border: 'border-warm-orange/25' },
  con: { labelKey: 'page.report.argument_con.label', color: 'text-cyan', border: 'border-cyan/25' },
} as const satisfies Record<'pro' | 'con', { labelKey: PlainMessageKey; color: string; border: string }>

/** 0–1 小数转百分比。null（读不出来）显示 "—"，绝不产出 "NaN%"——本仓库刚因为
 *  把三档字符串当小数乘 100 而满页 NaN%。 */
function confidencePct(value: number | null): string {
  return value === null ? DASH : formatPercent(value)
}

/** confidence_changes 的 before/after 已经是百分点整数，不能再乘 100。 */
function pointPct(value: number | null): string {
  return value === null ? DASH : formatPercent(Math.round(value) / 100)
}

/** 带正号的增量；null 显示 "—"。0 也照实显示成 0，不省略。 */
function signedNumber(value: number | null, digits: number): string {
  if (value === null) return DASH
  const fixed = Number(value.toFixed(digits))
  // 先按 digits 定精度，再交给 formatNumber 出千分位/小数点（英文界面是 "1.5"、
  // 中文界面也是 "1.5"，但小数点在别的 locale 会变）。不传 digits 给 formatNumber：
  // 那会把 0.1 补成 "0.10"，与原来 Number(toFixed()) 去尾零的显示不一致。
  // 正号得自己补：负号由 Intl 出，正号不出。
  return `${fixed > 0 ? '+' : ''}${formatNumber(fixed)}`
}

/**
 * 引擎的 limitation 里带 markdown 粗体标记（`**一次仲裁式反驳轮**`）。这段话
 * 必须逐字展示（docs 引用它，措辞本身就是承诺），所以既不能删标记改写，也不该
 * 走 dangerouslySetInnerHTML —— 拆成 React 节点渲染，标记生效、文字不动。
 */
function renderEmphasis(text: string): ReactNode[] {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .filter((chunk) => chunk !== '')
    .map((chunk, i) =>
      chunk.startsWith('**') && chunk.endsWith('**') && chunk.length > 4
        ? <strong key={i} className="font-semibold text-text-primary">{chunk.slice(2, -2)}</strong>
        : <span key={i}>{chunk}</span>
    )
}

function CrossExamArgumentBlock({ arg, role, live }: { arg: CrossExamArgument; role: 'pro' | 'con'; live: boolean }) {
  const meta = CROSS_EXAM_SIDE_META[role]
  const severity = VALID_SEVERITIES.includes(arg.severity as Severity) ? (arg.severity as Severity) : null
  return (
    <div className={cn('rounded-lg border bg-bg-secondary/40 p-3', meta.border)}>
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <span className={cn('text-xs font-medium', meta.color)}>{t(meta.labelKey)}</span>
        {arg.argument_id && (
          <span className="rounded bg-bg-card px-1.5 font-mono text-xs text-text-muted">{arg.argument_id}</span>
        )}
        {/* pro_args/con_args 里的 persona_id 放的是展示名（引擎历史口径） */}
        {arg.persona_id && <span className="text-xs text-text-secondary">{arg.persona_id}</span>}
        {/* severity 为空串时不画徽标：默认成"中"等于替引擎编了一个判定 */}
        {severity && <SeverityBadge severity={severity} />}
      </div>
      <p className="whitespace-pre-line text-xs text-text-primary">{arg.point}</p>
      {arg.rebuttal ? (
        <div className="mt-2 border-l-2 border-brand-primary/50 bg-bg-card/60 py-1.5 pl-2.5">
          <p className="mb-0.5 flex items-center gap-1 text-[11px] text-text-muted">
            <MessageSquareQuote className="h-3 w-3" strokeWidth={1.5} />
            {t('page.report.argument.label')}
          </p>
          <p className="whitespace-pre-line text-xs text-text-secondary">{arg.rebuttal}</p>
        </div>
      ) : (
        // 只在真跑过反驳轮时才说"未产出反驳"；派生摘要档本来就没人反驳过，
        // 逐条写"未产出"只会让人以为这是一次失败。
        live && arg.argument_id && (
          <p className="mt-2 text-[11px] text-text-muted">{t('page.report.argument.empty')}</p>
        )
      )}
    </div>
  )
}

/** 改票 / 未采纳改票共用一张卡。accepted=false 时措辞必须是"模型声称改为"——
 *  suppressed_changes 里的 to_stance 是被代码驳回的主张，不是最终立场。 */
function CrossExamChangeCard({
  change,
  accepted,
  fallbackThreshold,
}: {
  change: CrossExamVoteChange
  accepted: boolean
  fallbackThreshold: number | null
}) {
  const threshold = change.threshold ?? fallbackThreshold
  return (
    <div
      className={cn(
        'rounded-lg border p-3',
        accepted ? 'border-brand-primary/25 bg-brand-primary/5' : 'border-border bg-bg-secondary/40'
      )}
    >
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        {/* vote_changes 的 persona_id 是**真 id**，展示要用 persona_name */}
        <span className="text-sm font-medium text-text-primary">
          {change.persona_name || change.persona_id || t('page.report.change.empty')}
        </span>
        {change.argument_id && (
          <span className="rounded bg-bg-card px-1.5 font-mono text-xs text-text-muted">{change.argument_id}</span>
        )}
        {change.topic && <span className="text-xs text-text-muted">{change.topic}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {/* from_stance / to_stance 是引擎的立场枚举原词（wire key），永不翻译 */}
        <span className="rounded bg-bg-secondary px-1.5 py-0.5 text-text-secondary">{change.from_stance || DASH}</span>
        {accepted ? (
          <ArrowRightLeft className="h-3.5 w-3.5 shrink-0 text-brand-primary" strokeWidth={1.5} />
        ) : (
          <MinusCircle className="h-3.5 w-3.5 shrink-0 text-text-muted" strokeWidth={1.5} />
        )}
        <span
          className={cn(
            'rounded px-1.5 py-0.5',
            accepted ? 'bg-brand-primary/10 text-brand-primary' : 'text-text-muted line-through'
          )}
        >
          {accepted
            ? change.to_stance || DASH
            : t('page.report.change.badge', { stance: change.to_stance || DASH })}
        </span>
      </div>
      <p className="mt-1.5 text-xs text-text-muted">
        {threshold !== null
          ? t('page.report.change_threshold.label', {
              before: confidencePct(change.confidence_before),
              after: confidencePct(change.confidence_after),
              delta: signedNumber(change.delta, 2),
              threshold,
            })
          : t('page.report.change.label', {
              before: confidencePct(change.confidence_before),
              after: confidencePct(change.confidence_after),
              delta: signedNumber(change.delta, 2),
            })}
      </p>
      {/* suppressed_reason / reason 都是引擎回传的自由文本，只翻前缀不翻内容 */}
      {!accepted && change.suppressed_reason && (
        <p className="mt-1.5 text-xs text-severity-medium">
          {t('page.report.change.error', { reason: change.suppressed_reason })}
        </p>
      )}
      {change.reason && (
        <p className="mt-1.5 whitespace-pre-line text-xs text-text-secondary">
          {t('page.report.change.desc', { reason: change.reason })}
        </p>
      )}
    </div>
  )
}

/**
 * 交叉质询区块。
 *
 * 这一节的展示规则来自引擎侧的六条底线（见 src/runner/cross_exam.py 顶部注释），
 * 其中三条直接决定这里怎么画：
 *   1. 三档模式（派生摘要 / 仲裁式反驳 / 多智能体反驳）是三件不同的事，必须
 *      在页面上分得清——派生摘要档要明确写"未进行反驳轮"，不能靠留白暗示；
 *   2. 反驳失败要如实显示，不能与"本来就没有争议点"长成一样；
 *   3. 没有人改票是完全正常的结果，要写出来，不能留一片空白让人以为渲染坏了。
 *
 * 传进来的 view 已经在 toCrossExamView() 里做过运行时收敛，这里不再有 as 断言。
 */
function CrossExamSection({ view }: { view: CrossExamView }) {
  // 老 v1 后端把模型原始输出的数组直接存进了这个字段，解不出争议点与改票明细。
  // 硬解等于把猜测当事实，如实说明即可。
  if (view.is_legacy_array) {
    return (
      <div className="mb-6">
        <div className="mb-4 flex items-center gap-2">
          <Swords className="h-5 w-5 text-text-muted" strokeWidth={1.25} />
          <h3 className="text-lg font-semibold text-text-primary">{t('page.report.cross_exam.title')}</h3>
        </div>
        <div className="rounded-xl border border-border bg-bg-card p-4 text-sm text-text-secondary md:p-5">
          {t('page.report.cross_exam_legacy.desc', { count: view.legacy_entry_count })}
        </div>
      </div>
    )
  }

  const live = view.is_live_debate
  const modeLabel = view.mode
    ? t(CROSS_EXAM_MODE_LABEL_KEYS[view.mode])
    : view.mode_raw
      ? t('page.report.cross_exam_mode_unknown.value', { raw: view.mode_raw })
      : t('page.report.cross_exam_mode_unknown.label')
  const modeBadgeClass = view.mode ? CROSS_EXAM_MODE_BADGE[view.mode] : 'bg-severity-medium/10 text-severity-medium border-severity-medium/30'
  const modeDescription = view.mode
    ? t(CROSS_EXAM_MODE_DESC_KEYS[view.mode])
    : t('page.report.cross_exam_mode_unknown.desc')
  // 请求的档位跑不成会回落，落差本身是用户该知道的信息
  const fellBack = view.requested_mode !== null && view.mode !== null && view.requested_mode !== view.mode
  const hasFailures = view.failures.length > 0
  // 引擎那句 limitation 的显示强度按实际情况分三档，不一律标红也不一律缩成小字：
  //   alert —— 真挂了（有 failures），是坏消息；
  //   info  —— 只是回落（比如没有可反驳的对立论据），是"没跑成但也不算故障"；
  //   muted —— 一切正常，它只是补充说明。
  // 全部拉到最高档会让真正的失败贬值，全压成小字又等于藏起来。
  const limitationTone: 'alert' | 'info' | 'muted' =
    view.limitation === '' ? 'muted' : hasFailures ? 'alert' : fellBack ? 'info' : 'muted'

  return (
    <div className="mb-6">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Swords className={cn('h-5 w-5', live ? 'text-brand-primary' : 'text-text-muted')} strokeWidth={1.25} />
        <h3 className="text-lg font-semibold text-text-primary">{t('page.report.cross_exam.title')}</h3>
        <span className={cn('rounded border px-2 py-0.5 text-xs font-medium', modeBadgeClass)}>{modeLabel}</span>
        {live && view.rounds_run > 0 && (
          <span className="text-xs text-text-muted">{t('page.report.cross_exam.badge', { count: view.rounds_run })}</span>
        )}
      </div>

      {/* 模式说明：用户有权知道自己这份报告是三档里的哪一种 */}
      <div
        className={cn(
          'mb-3 rounded-xl border p-4 text-sm md:p-5',
          live ? 'border-border bg-bg-card text-text-primary' : 'border-border bg-bg-secondary/40 text-text-secondary'
        )}
      >
        <p>{modeDescription}</p>
        {fellBack && (
          <p className="mt-2 text-xs text-severity-medium">
            {t('page.report.cross_exam_fallback.desc', {
              requested: view.requested_mode
                ? t(CROSS_EXAM_MODE_LABEL_KEYS[view.requested_mode])
                : view.requested_mode_raw ?? t('page.report.cross_exam_mode_unknown.label'),
              actual: modeLabel,
            })}
          </p>
        )}
        {view.limitation && limitationTone === 'muted' && (
          // limitation 是引擎原文（带 markdown 粗体标记），逐字展示、只翻前缀
          <p className="mt-2 text-xs text-text-muted">
            {t('page.report.cross_exam_limitation.label')}
            {renderEmphasis(view.limitation)}
          </p>
        )}
      </div>

      {limitationTone !== 'muted' && (
        <div
          className={cn(
            'mb-3 rounded-xl p-4',
            limitationTone === 'alert'
              ? 'border-2 border-warm-orange bg-warm-orange/10'
              : 'border border-severity-medium/40 bg-severity-medium/5'
          )}
        >
          <div className="flex items-start gap-3">
            {limitationTone === 'alert' ? (
              <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-warm-orange" strokeWidth={1.75} />
            ) : (
              <Info className="mt-0.5 h-5 w-5 shrink-0 text-severity-medium" strokeWidth={1.5} />
            )}
            <p className="text-sm text-text-primary">{renderEmphasis(view.limitation)}</p>
          </div>
        </div>
      )}

      {/* 失败逐条列出。吞掉失败正是这个仓库在系统性清除的模式：
          "跑了但挂了"和"本来就没有争议点"在页面上必须长得不一样。 */}
      {hasFailures && (
        <div className="mb-3 rounded-xl border border-severity-critical/40 bg-severity-critical/5 p-4 md:p-5">
          <div className="mb-2 flex items-center gap-2">
            <XCircle className="h-4 w-4 text-severity-critical" strokeWidth={1.5} />
            <h4 className="text-sm font-medium text-severity-critical">
              {t('page.report.cross_exam_failures.title', { count: view.failures.length })}
            </h4>
          </div>
          <ul className="space-y-1">
            {view.failures.map((f, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-1.5 text-xs text-text-secondary">
                <span className="rounded bg-bg-secondary px-1.5 font-mono text-text-muted">
                  {[f.stage, f.point_id, f.argument_id].filter(Boolean).join(' · ') ||
                    t('page.report.cross_exam_failures.label')}
                </span>
                <span>{f.error || t('page.report.cross_exam_failures.empty')}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 争议点 + 双方论据 + 反驳 */}
      {view.disputes.length > 0 ? (
        <div className="mb-3 flex flex-col gap-3">
          {view.disputes.map((d, i) => (
            <div key={d.point_id || i} className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                {d.point_id && (
                  <span className="rounded bg-bg-secondary px-1.5 font-mono text-xs text-text-muted">{d.point_id}</span>
                )}
                <p className="flex-1 text-sm font-medium text-text-primary">
                  {d.topic || t('page.report.dispute.empty')}
                </p>
                <span className={cn('rounded px-2 py-0.5 text-xs font-medium', REBUTTAL_STATUS_CLASSES[d.rebuttal_status])}>
                  {t(REBUTTAL_STATUS_KEYS[d.rebuttal_status])}
                </span>
              </div>
              {d.rebuttal_status !== 'ok' && d.rebuttal_error && (
                <p className="mb-3 text-xs text-severity-medium">
                  {t('page.report.dispute.error', { reason: d.rebuttal_error })}
                </p>
              )}
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {d.pro_args.map((arg, j) => (
                  <CrossExamArgumentBlock key={arg.argument_id || `pro-${j}`} arg={arg} role="pro" live={live} />
                ))}
                {d.con_args.map((arg, j) => (
                  <CrossExamArgumentBlock key={arg.argument_id || `con-${j}`} arg={arg} role="con" live={live} />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        // 空争议点不留白：说清楚是"没找到分歧"还是"这一步没跑成"。
        // 上面已经把引擎给的具体原因摆出来了，就不要在这里另编一个原因——
        // "没有可反驳的论据正文"和"大家意见一致"是两回事。
        <div className="mb-3 rounded-xl border border-border bg-bg-card p-4 text-sm text-text-secondary md:p-5">
          {limitationTone === 'muted'
            ? t('page.report.dispute_empty.desc')
            : t('page.report.dispute_empty.hint')}
        </div>
      )}

      {/* 改票记录。"没有人改票"是正常结果，必须写出来而不是留空白。 */}
      <div className="mb-3 rounded-xl border border-border bg-bg-card p-4 md:p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <ArrowRightLeft className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
          <h4 className="text-sm font-semibold text-text-primary">{t('page.report.vote.title')}</h4>
          {live && (
            <span className="text-xs text-text-muted">
              {view.threshold !== null
                ? t('page.report.vote_threshold.badge', {
                    count: view.vote_changes.length,
                    threshold: view.threshold,
                  })
                : t('page.report.vote.badge', { count: view.vote_changes.length })}
            </span>
          )}
        </div>
        {!live ? (
          <p className="text-sm text-text-secondary">
            {t('page.report.vote.empty')}
          </p>
        ) : view.vote_changes.length === 0 ? (
          <p className="text-sm text-text-secondary">
            {t('page.report.vote_unchanged.desc')}
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {view.vote_changes.map((vc, i) => (
              <CrossExamChangeCard
                key={`${vc.argument_id}-${i}`}
                change={vc}
                accepted
                fallbackThreshold={view.threshold}
              />
            ))}
          </div>
        )}

        {/* 模型想改票但代码没采纳：这一条不显示出来，用户会误以为模型压根没动摇过 */}
        {view.suppressed_changes.length > 0 && (
          <div className="mt-4 border-t border-border pt-3">
            <p className="mb-2 text-xs text-text-muted">
              {view.allow_stance_update
                ? t('page.report.suppressed.desc', { count: view.suppressed_changes.length })
                : t('page.report.suppressed_no_update.desc', { count: view.suppressed_changes.length })}
            </p>
            <div className="flex flex-col gap-2">
              {view.suppressed_changes.map((sc, i) => (
                <CrossExamChangeCard
                  key={`${sc.argument_id}-suppressed-${i}`}
                  change={sc}
                  accepted={false}
                  fallbackThreshold={view.threshold}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 逐人格置信度变化：只在真跑过反驳时有意义（派生摘要档 delta 恒为 0，
          画出来只会让人以为发生过一场辩论） */}
      {live && view.confidence_changes.length > 0 && (
        <div className="mb-3 rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <h4 className="mb-3 text-sm font-semibold text-text-primary">{t('page.report.confidence.title')}</h4>
          <ul className="flex flex-col gap-2">
            {view.confidence_changes.map((cc, i) => {
              const delta = cc.delta
              const Icon = delta === null || delta === 0 ? Minus : delta > 0 ? TrendingUp : TrendingDown
              const deltaClass =
                delta === null || delta === 0
                  ? 'text-text-muted'
                  : delta > 0
                    ? 'text-brand-primary'
                    : 'text-severity-medium'
              return (
                <li key={cc.persona_key || `${cc.persona_id}-${i}`} className="flex flex-wrap items-center gap-2 text-xs">
                  {/* confidence_changes 的 persona_id 是展示名（引擎历史口径） */}
                  <span className="min-w-24 text-text-primary">
                    {cc.persona_id || cc.persona_key || t('page.report.change.empty')}
                  </span>
                  <span className="text-text-secondary">
                    {pointPct(cc.before)} → {pointPct(cc.after)}
                  </span>
                  <span className={cn('flex items-center gap-1', deltaClass)}>
                    <Icon className="h-3 w-3" strokeWidth={1.5} />
                    {delta === null ? DASH : t('page.report.confidence.unit', { delta: signedNumber(delta, 0) })}
                  </span>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      {/* 这一节是真花钱的模型调用，用量摆出来；拿不到 token 数就说明成本可能偏低。
          calls 在引擎里按**尝试**计（失败的调用也算一次），文案必须跟着这个口径写，
          否则"1 次调用 / 0 tokens"看起来像个 bug。 */}
      {view.usage && view.usage.calls > 0 && (
        <p className="text-xs text-text-muted">
          {t('page.report.usage.desc', {
            calls: view.usage.calls,
            input: formatNumber(view.usage.input_tokens),
            output: formatNumber(view.usage.output_tokens),
          })}
          {!view.usage.token_counts_available && t('page.report.usage.hint')}
        </p>
      )}

      {/* θ 没读到配置、走了内置默认值时才提——正常读到 yaml 时展示文件路径只是噪音 */}
      {view.threshold_source.startsWith('fallback-default') && (
        <p className="mt-1 text-xs text-severity-medium">
          {t('page.report.threshold.error', { source: view.threshold_source })}
        </p>
      )}
    </div>
  )
}

export default function ReportPage() {
  // 顶层调用一次：它内部 useLocale()，所以本页也顺带订阅了 ui_lang，
  // 切语言时整页重渲染、t() 的结果跟着变（契约 6.3）。
  useDocumentTitle('page.report.meta.title')
  const { id } = useParams()
  // persona_notes 等报告字段只带 persona_id / persona_name（恒中文，10.3 红线）；
  // 英文界面下换成 display_name_en 要靠这份人格库反查，同 ReviewProgressPage
  // 的用法——全局 store，其它页面（PersonasPage 等）已经拉过的话这里直接复用。
  const { personas: personaCatalog, initPersonas: initPersonaCatalog, initialized: personaCatalogInitialized } = usePersonaStore()
  useEffect(() => {
    if (!personaCatalogInitialized) initPersonaCatalog()
  }, [personaCatalogInitialized, initPersonaCatalog])
  const [review, setReview] = useState<Review | null>(null)
  const [report, setReport] = useState<RealReport | null>(null)
  const [calibration, setCalibration] = useState<RealCalibration | null>(null)
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null)
  const [reportHtml, setReportHtml] = useState<string | null>(null)
  /** HTML 版本为什么没有。以前 /result 的失败是 `.catch(() => {})`，HTML 按钮
   *  照样亮着，点下去下载一张只写着「HTML报告尚未生成」的白页——用户会以为
   *  自己的报告内容丢了。现在原因如实留着，按钮也不再假装可用。 */
  const [htmlUnavailable, setHtmlUnavailable] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  // 加载失败必须留痕：以前 catch 里什么都不存，网络错误/403/500 全落到
  // "报告尚未生成"那一句上，用户既不知道原因也没法重试。
  const [loadError, setLoadError] = useState<Error | null>(null)
  // 重试就是把加载 effect 重跑一遍（数据全在 effect 里取，没有别的入口）
  const [reloadNonce, setReloadNonce] = useState(0)
  const [expandedIssues, setExpandedIssues] = useState<Set<number>>(new Set())
  const [showHtmlReport, setShowHtmlReport] = useState(false)
  const [evaluationScorecard, setEvaluationScorecard] = useState<EvaluationScorecard | null>(null)
  // 存收敛后的视图：违规项与风险档位在进 state 前就已经过类型守卫
  const [ethicsReports, setEthicsReports] = useState<EthicsReportView[]>([])
  const [expandedDimensions, setExpandedDimensions] = useState<Set<string>>(new Set())
  const [evaluating, setEvaluating] = useState(false)
  const [evaluationError, setEvaluationError] = useState<string | null>(null)
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [feedbackUseful, setFeedbackUseful] = useState<boolean | null>(null)
  const [decisionChanged, setDecisionChanged] = useState(false)
  const [adoptedFixes, setAdoptedFixes] = useState<string[]>([])
  const [hoursSaved, setHoursSaved] = useState(0)
  const [willingnessToPay, setWillingnessToPay] = useState(0)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  // ---- 只读分享链接 ----
  // 初值来自 review.share_token（后端只回给作者本人），之后由本页的
  // 开启/撤销动作维护，不再回头依赖 review——否则撤销后按钮还显示"已公开"。
  const [shareToken, setShareToken] = useState<string | null>(null)
  const [sharePanelOpen, setSharePanelOpen] = useState(false)
  const [shareBusy, setShareBusy] = useState(false)
  const [shareError, setShareError] = useState<string | null>(null)
  const [shareCopied, setShareCopied] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    setShareToken(review?.share_token ?? null)
  }, [review?.share_token])

  const shareUrl = shareToken ? `${window.location.origin}/s/${shareToken}` : null

  const handleShare = async () => {
    if (!id || shareBusy) return
    setShareBusy(true)
    setShareError(null)
    try {
      const r = await api.shareReview(id)
      setShareToken(r.share_token)
    } catch (e) {
      setShareError(tApiError(e, 'page.report.share.error'))
    } finally {
      setShareBusy(false)
    }
  }

  const handleUnshare = async () => {
    if (!id || shareBusy) return
    setShareBusy(true)
    setShareError(null)
    try {
      await api.unshareReview(id)
      setShareToken(null)
      setShareCopied(false)
    } catch (e) {
      setShareError(tApiError(e, 'page.report.share_revoke.error'))
    } finally {
      setShareBusy(false)
    }
  }

  const handleCopyShareUrl = async () => {
    if (!shareUrl) return
    try {
      await navigator.clipboard.writeText(shareUrl)
      setShareCopied(true)
      setTimeout(() => setShareCopied(false), 2000)
    } catch {
      // 剪贴板 API 在非 HTTPS/无权限时会拒绝。不弹"复制成功"的假消息——
      // 链接本身就在输入框里显示着，用户可以自己选中复制。
      setShareError(t('page.report.share_copy.error'))
    }
  }

  const toggleIssue = (index: number) => {
    setExpandedIssues((prev) => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  useEffect(() => {
    if (!id) return
    let alive = true

    const loadData = async () => {
      const [reviewData, reportData] = await Promise.all([fetchReview(id), fetchReport(id)])
      if (!alive) return
      setReview(reviewData)
      if (reportData.report_json) {
        setReport(reportData.report_json as unknown as RealReport)
      }
      if (reportData.calibration) {
        setCalibration(reportData.calibration as RealCalibration)
      }
      if (reportData.report_markdown) {
        setReportMarkdown(reportData.report_markdown)
      }
      // 匿名看的这份报告，归属还挂在共享的 anonymous 桶里。记下 id，用户登录/
      // 注册时才认领得回来（见 apiClient 的待认领清单）——否则登录那一刻它就 404。
      if (!getToken()) rememberPendingReview(id)
    }

    const run = async () => {
      setLoading(true)
      setLoadError(null)
      try {
        await loadData()
      } catch (firstError) {
        // 已登录却打不开：很可能就是"这条评审是登录前匿名跑的，还挂在 anonymous
        // 名下"。认领一次再重试；这里是兜底路径（正常路径在登录时就认领了），
        // 覆盖"在别的标签页登录""事后再打开这个链接"这类情况。
        let recovered = false
        try {
          const claimed = await claimPendingReviews()
          if (claimed.includes(id)) {
            await loadData()
            recovered = true
          }
        } catch {
          // 认领这条兜底路径自己也失败了（未登录/限流/后端不支持）。它的失败原因
          // 对用户没有意义——真正该看到的是下面那个"第一次加载为什么失败"。
        }
        // 兜底没救回来就把最初的错误如实抛给用户。此前这里什么都不做，
        // 于是 403/500/断网全都伪装成了"报告尚未生成"。
        if (!recovered && alive) {
          setLoadError(firstError instanceof Error ? firstError : new Error(String(firstError)))
        }
      } finally {
        if (alive) setLoading(false)
      }
    }

    void run()
    return () => {
      alive = false
    }
  }, [id, reloadNonce])

  useEffect(() => {
    if (!id) return
    // 依赖里不能有 reportMarkdown：setReportMarkdown 会再触发一次本 effect，
    // 白白多打一次 /result。加载 HTML/MD 只跟评审 id 有关，跑一次即可；
    // 里面 !reportMarkdown 的守卫是为了不覆盖上方 loadData 已取到的 markdown。
    fetchReviewResult(id)
      .then((result) => {
        // html_error 是后端 ReviewResult schema 里真实存在的字段（渲染失败的原因），
        // 但前端的 ReviewResultData 类型里还没有它，所以在这里就地放宽——
        // 那个类型定义在 lib/mock-data.ts，不归本次改动范围。
        const withError = result as typeof result & { html_error?: string | null }
        if (result.report_html) {
          setReportHtml(result.report_html)
          setHtmlUnavailable(null)
        } else {
          setHtmlUnavailable(
            withError.html_error?.trim() || t('page.report.html.empty')
          )
        }
        if (result.report_md && !reportMarkdown) setReportMarkdown(result.report_md)
      })
      .catch((error: unknown) => {
        setHtmlUnavailable(
          t('page.report.html.error', { reason: tApiError(error, 'common.ui.unknown_error') })
        )
      })
  }, [id])

  useEffect(() => {
    if (!id) return
    fetchEvaluation(id).then(setEvaluationScorecard).catch(() => {})
    fetchEthicsReport(id).then((reports) => setEthicsReports(reports.map(toEthicsReportView))).catch(() => {})
  }, [id])

  useEffect(() => {
    if (reportHtml && iframeRef.current) {
      const doc = iframeRef.current.contentDocument
      if (doc) {
        doc.open()
        doc.write(reportHtml)
        doc.close()
      }
    }
  }, [reportHtml, showHtmlReport])

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <Loader2 className="w-8 h-8 text-cyan animate-spin mx-auto mb-4" strokeWidth={1.25} />
        <p className="text-text-secondary">{t('page.report.body.loading')}</p>
      </div>
    )
  }

  if (loadError) {
    return <ReportLoadError error={loadError} reviewId={id} onRetry={() => setReloadNonce((n) => n + 1)} />
  }

  // 失败态优先于一切渲染分支（含体验版）：失败的评审没有"部分内容"可展示，
  // 匿名裁剪也会把 {"error": ...} 原样透出（report_gating 专门留了这个分支）。
  const failure = reviewFailure(review, report)
  if (failure) {
    return <ReviewFailedNotice reviewId={id} review={review} reason={failure.reason} />
  }

  if (report?.is_gated) {
    return <GatedReportTeaser review={review} gated={report} />
  }

  if (!review || !report) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <p className="text-text-secondary">{t('page.report.pending.title')}</p>
        <p className="mt-2 text-sm text-text-muted">{t('page.report.pending.desc')}</p>
        <Link to={`/review/${id}`} className="text-cyan hover:text-cyan-dim mt-4 inline-block">
          {t('page.report.pending.cta')}
        </Link>
      </div>
    )
  }

  const summary = report.executive_summary
  // 认不出的等级（含缺失）走 UNKNOWN_RISK 显示「—」，不再兜底成中风险
  const risk = RISK_CONFIG[summary?.release_risk ?? ''] ?? null
  const riskView = risk ?? UNKNOWN_RISK
  const reviewMode = (review.mode ?? 'standard') as ReviewMode
  const modeBadge = MODE_BADGE[reviewMode] ?? MODE_BADGE.standard
  const priorityFixes = report.priority_fixes ?? []
  const personaNotes = report.persona_notes ?? []
  const disagreements = report.major_disagreements ?? []
  const informationGaps = report.information_gaps ?? []
  // null 只代表"这份报告没有交叉质询区块"（quick 档不跑 / 老报告没这个键）；
  // "跑了但失败了"仍然是个区块，会带 failures，必须渲染出来。
  const crossExam = toCrossExamView(report.cross_examination)

  // 立场分布由 persona_notes 现场统计（引擎不单独输出这一项）
  const stanceCounts = new Map<string, number>()
  for (const note of personaNotes) {
    const s = noteStance(note)
    stanceCounts.set(s, (stanceCounts.get(s) ?? 0) + 1)
  }
  const stanceData = Array.from(stanceCounts.entries()).map(([name, value], i) => ({
    name,
    value,
    color: STANCE_PALETTE[i % STANCE_PALETTE.length],
  }))

  const handleExport = (format: 'json' | 'markdown' | 'html') => {
    let content: string
    let mimeType: string
    let ext: string

    if (format === 'json') {
      content = JSON.stringify(report, null, 2)
      mimeType = 'application/json'
      ext = 'json'
    } else if (format === 'html') {
      // 没有 HTML 就什么都不下载。造一张写着"尚未生成"的白页当报告发出去，
      // 用户拿到的是一个看起来像损坏文件的东西，还会以为内容丢了。
      if (!reportHtml) return
      content = reportHtml
      mimeType = 'text/html'
      ext = 'html'
    } else {
      content = reportMarkdown ?? generateMarkdown(report)
      mimeType = 'text/markdown'
      ext = 'md'
    }

    const blob = new Blob([content], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `report-${review.id}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 animate-fade-in">
      {/* 三条诚实信号一律置顶，不滚动就能看到：合成声明（ETHICS.md 强制）、
          模拟占位输出、人格降级。它们比报告结论本身更需要被先看到。
          max-w-3xl 与正文同宽——正文阅读列收窄后，全宽横幅会显得比正文"更重要" */}
      <div className="max-w-3xl mx-auto">
      <SyntheticBanner />
      {report.simulation_notice && (
        <div className="mb-4 rounded-xl border-2 border-severity-critical bg-severity-critical/10 p-4 text-sm font-bold text-severity-critical md:text-base">
          {report.simulation_notice}
        </div>
      )}
      <DegradationNotice degradation={report.degradation} />
      <SkillDegradedNotice notice={review?.skill_degraded} />
      <ValidationGateNotice validation={report.validation} />
      <BudgetNotice budget={report.budget} />
      <PanelSelectionNotice panelSelection={report.panel_selection} />
      </div>

      {/* 页面头部独立成全宽一行：标题 + 操作组，和下面收窄的正文阅读列分层。
          分享/导出按钮原本跟在标题行尾部，现在收拢成一个胶囊分组，不再东一个西一个 */}
      <div className="mb-6 flex flex-wrap items-center gap-3 border-b border-border pb-4">
        <Link to={`/review/${id}`} className="p-2 rounded-lg hover:bg-bg-card transition-colors">
          <ArrowLeft className="w-5 h-5 text-text-secondary" strokeWidth={1.25} />
        </Link>
        <div className="flex-1 min-w-[12rem]">
          <h1 className="text-xl font-semibold text-text-primary truncate">
            {review.target_title || report.meta?.target || t('page.report.header.title')}
          </h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-text-secondary">{t('page.report.header.subtitle')}</p>
            <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', modeBadge.bg, modeBadge.color)}>
              <modeBadge.Icon className="w-3 h-3" strokeWidth={1.5} />
              {t('page.report.header.badge', { mode: t(modeBadge.labelKey) })}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0 rounded-xl border border-border bg-bg-card p-1">
          <button
            onClick={() => setSharePanelOpen((v) => !v)}
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm transition-all',
              shareToken
                ? 'bg-brand-primary/10 text-brand-primary'
                : 'text-text-secondary hover:bg-bg-card-hover hover:text-brand-primary'
            )}
          >
            <Share2 className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">
              {shareToken ? t('page.report.share.badge') : t('page.report.share.cta')}
            </span>
          </button>
          <button
            onClick={() => handleExport('json')}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm text-text-secondary hover:bg-bg-card-hover hover:text-brand-primary transition-all"
          >
            <File className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">JSON</span>
          </button>
          <button
            onClick={() => handleExport('markdown')}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm text-text-secondary hover:bg-bg-card-hover hover:text-cyan transition-all"
          >
            <FileText className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">MD</span>
          </button>
          <button
            onClick={() => handleExport('html')}
            disabled={!reportHtml}
            title={reportHtml ? undefined : htmlUnavailable ?? t('page.report.html.tooltip')}
            className={cn(
              'flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm transition-all',
              reportHtml
                ? 'text-text-secondary hover:bg-bg-card-hover hover:text-warm-orange'
                : 'text-text-muted cursor-not-allowed'
            )}
          >
            <Globe className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">HTML</span>
          </button>
        </div>
      </div>

      {/* 正文阅读列收窄到 3xl 居中：报告是长阅读场景，4xl 容器里单行字数过长；
          图表/表格类容器统一加 overflow-x-auto 兜底，超宽内容在列内滚动而不是撑破 */}
      <div className="max-w-3xl mx-auto">

      {/* 分享面板。
          这里的"对方能看到 / 看不到"两栏不是装饰，是知情同意的正文：报告里
          可能有还没发布的产品材料和定价策略，用户按下"生成链接"之前必须
          知道自己在公开什么。两栏内容与后端白名单（share_service.to_public_dict）
          一一对应，改后端就要改这里，否则这段说明会变成一句谎话。 */}
      {sharePanelOpen && (
        <div className="mb-6 rounded-xl border border-border bg-bg-card p-5">
          <div className="flex items-start gap-2.5">
            <Share2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-primary" strokeWidth={1.5} />
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold text-text-primary">{t('page.report.share.title')}</h3>
              <p className="mt-1 text-xs text-text-secondary">
                <Trans
                  k="page.report.share.desc"
                  slots={{ emph: (s) => <strong className="text-text-primary">{s}</strong> }}
                />
              </p>

              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-border bg-bg-secondary/50 p-3">
                  <div className="text-[11px] font-semibold text-text-secondary mb-1.5">
                    {t('page.report.share_visible.label')}
                  </div>
                  <ul className="space-y-1 text-[11px] text-text-muted">
                    <li>{t('page.report.share_item_report.label')}</li>
                    <li>{t('page.report.share_item_meta.label')}</li>
                    <li>{t('page.report.share_item_calibration.label')}</li>
                  </ul>
                </div>
                <div className="rounded-lg border border-border bg-bg-secondary/50 p-3">
                  <div className="text-[11px] font-semibold text-text-secondary mb-1.5">
                    {t('page.report.share_hidden.label')}
                  </div>
                  <ul className="space-y-1 text-[11px] text-text-muted">
                    <li>{t('page.report.share_item_account.label')}</li>
                    <li>{t('page.report.share_item_cost.label')}</li>
                    <li>{t('page.report.share_item_material.label')}</li>
                  </ul>
                </div>
              </div>

              {shareError && (
                <p className="mt-3 flex items-start gap-1.5 text-xs text-severity-critical">
                  <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
                  <span className="break-all">{shareError}</span>
                </p>
              )}

              {shareToken && shareUrl ? (
                <div className="mt-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      readOnly
                      value={shareUrl}
                      onFocus={(e) => e.currentTarget.select()}
                      aria-label={t('page.report.share.aria')}
                      className="min-w-0 flex-1 rounded-md border border-border bg-bg-secondary px-3 py-2 font-mono text-xs text-text-primary outline-none"
                    />
                    <button
                      onClick={() => void handleCopyShareUrl()}
                      className="flex items-center gap-1.5 rounded-md border border-border bg-bg-card px-3 py-2 text-xs text-text-primary transition-colors hover:border-brand-primary/40"
                    >
                      {shareCopied ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-brand-primary" strokeWidth={1.5} />
                      ) : (
                        <Copy className="h-3.5 w-3.5" strokeWidth={1.5} />
                      )}
                      {shareCopied ? t('common.ui.copied') : t('common.action.copy')}
                    </button>
                    <button
                      onClick={() => void handleUnshare()}
                      disabled={shareBusy}
                      className="flex items-center gap-1.5 rounded-md border border-severity-critical/30 bg-severity-critical/5 px-3 py-2 text-xs text-severity-critical transition-colors hover:bg-severity-critical/10 disabled:opacity-50"
                    >
                      {shareBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} /> : <Lock className="h-3.5 w-3.5" strokeWidth={1.5} />}
                      {t('page.report.share_revoke.cta')}
                    </button>
                  </div>
                  <p className="mt-2 text-[11px] text-text-muted">
                    {t('page.report.share.hint')}
                  </p>
                </div>
              ) : (
                <button
                  onClick={() => void handleShare()}
                  disabled={shareBusy}
                  className="mt-4 flex items-center gap-1.5 rounded-md bg-brand-primary px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-brand-primary-dim disabled:opacity-50"
                >
                  {shareBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} /> : <Share2 className="h-3.5 w-3.5" strokeWidth={1.5} />}
                  {t('page.report.share_create.cta')}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* HTML 版本缺席要说原因。禁用按钮的 title 只有把鼠标停上去才看得到，
          而这件事（"这份报告没有 HTML 版"还是"渲染坏了"）用户有权直接读到。 */}
      {!reportHtml && htmlUnavailable && (
        <div className="mb-6 flex items-start gap-2.5 rounded-xl border border-border bg-bg-secondary/40 p-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" strokeWidth={1.5} />
          <p className="text-xs text-text-secondary break-all">
            {t('page.report.html.desc', { reason: htmlUnavailable })}
          </p>
        </div>
      )}

      {reportHtml && (
        <div className="mb-6">
          <button
            onClick={() => setShowHtmlReport(!showHtmlReport)}
            className={cn(
              'w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-all',
              showHtmlReport
                ? 'bg-brand-primary/5 border-brand-primary/30'
                : 'bg-bg-card border-border hover:border-brand-primary/30'
            )}
          >
            <span className="flex items-center gap-2 text-sm font-medium text-text-secondary">
              <Globe className="w-4 h-4 text-brand-primary" strokeWidth={1.25} />
              {t('page.report.html.cta')}
            </span>
            {showHtmlReport
              ? <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
              : <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
            }
          </button>
          {showHtmlReport && (
            <div className="mt-3 rounded-xl border border-border overflow-x-auto bg-bg-card">
              <iframe
                ref={iframeRef}
                title={t('page.report.html.aria')}
                className="w-full border-0"
                style={{ height: '600px' }}
                sandbox="allow-same-origin"
              />
            </div>
          )}
        </div>
      )}

      {/* ---------- 执行摘要 / 发布风险 ---------- */}
      <div className={cn('rounded-xl border-2 p-4 md:p-6 mb-6', riskView.bg, riskView.border)}>
        <div className="flex items-center gap-3 mb-3">
          <AlertTriangle className={cn('w-5 h-5 md:w-6 md:h-6', riskView.color)} strokeWidth={1.25} />
          <h2 className={cn('text-base md:text-lg font-bold font-display', riskView.color)}>
            {t('page.report.summary.title', { risk: risk ? t(risk.labelKey) : DASH })}
          </h2>
        </div>
        {/* 缺等级要说是"报告没给"，不是"评估结果是中风险" */}
        {!risk && (
          <p className="mb-3 text-xs text-text-muted">
            {summary?.release_risk
              ? t('page.report.summary_risk_missing.desc', { raw: summary.release_risk })
              : t('page.report.summary_risk_absent.desc')}
          </p>
        )}
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <div>
            <dt className="text-xs text-text-muted">{t('page.report.summary_stance.label')}</dt>
            {/* primary_recommendation 是引擎的自由文本（产出物），原样透出 */}
            <dd className="mt-1 font-medium text-text-primary">{summary?.primary_recommendation || DASH}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">{t('page.report.summary_evidence.label')}</dt>
            <dd className="mt-1 font-medium text-text-primary">
              {evidenceQualityLabel(summary?.evidence_quality)}
            </dd>
          </div>
          <div>
            {/* 口径跟 aggregator.compute_consensus 的 docstring 对齐：
                agreed_points = 至少两位人格各自提到的同一议题；
                questioned_points = 只有个别人格提出的关切，不是"大家共同质疑"。
                写成"存疑点"会被读反。 */}
            <dt className="text-xs text-text-muted">{t('page.report.summary_consensus.label')}</dt>
            {/* 报告压根没有 consensus 区块时显示「—」：0/0 会被读成"跑过了、没找到共识问题"，
                和"这一节根本没产出"是两回事 */}
            <dd className="mt-1 font-medium text-text-primary">
              {report.consensus
                ? `${report.consensus.agreed_points?.length ?? 0} / ${report.consensus.questioned_points?.length ?? 0}`
                : DASH}
            </dd>
            {/* 判定口径来自引擎的 min_personas_for_agreement，不在前端重算——
                引擎改阈值时这里自动跟着变，两套口径并存正是要避免的坑 */}
            {typeof report.consensus?.min_personas_for_agreement === 'number' &&
              report.consensus.min_personas_for_agreement > 0 && (
                <p className="mt-0.5 text-xs text-text-muted">
                  {t('page.report.summary_consensus.hint', {
                    min: report.consensus.min_personas_for_agreement,
                    total: report.consensus.persona_count ?? '?',
                  })}
                </p>
              )}
          </div>
        </dl>
      </div>

      {/* ---------- 立场分布 + 校准指标 ---------- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <h3 className="text-sm font-medium text-text-muted mb-4">
            {t('page.report.stance.title', { count: personaNotes.length })}
          </h3>
          {stanceData.length > 0 ? (
            <>
              <div className="min-h-[180px] md:min-h-[220px]">
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={stanceData}
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={70}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {stanceData.map((d, i) => (
                        <Cell key={i} fill={d.color} fillOpacity={0.8} stroke={d.color} strokeWidth={1} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1c1c1e', border: '1px solid #38383a', borderRadius: '12px', fontSize: '12px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}
                      itemStyle={{ color: '#ffffff' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap justify-center gap-3 md:gap-4 mt-2">
                {stanceData.map((d) => (
                  <div key={d.name} className="flex items-center gap-1.5 text-xs">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                    <span className="text-text-secondary">{d.name}</span>
                    <span className="font-mono text-text-muted">{d.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="py-8 text-center text-xs text-text-muted">{t('page.report.stance.empty')}</p>
          )}
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5 overflow-x-auto">
          <h3 className="mb-4 text-base font-semibold text-text-primary">{t('page.report.calibration.title')}</h3>
          {calibration ? (
            <>
              {/* 合格线全部来自 src/runner/calibration.py::run_calibration_check：
                  overall_pass = role_consistency.average >= 0.8 且 coverage.average_distance >= 0.3。
                  无幻觉率**没有**参与 overall_pass，引擎里只有"单个人格幻觉率 > 0.5 记为高风险"
                  这一条，跟这里的平均值不是同一个量，所以不给它安合格线——
                  给一条编出来的线，就等于凭空判一个指标合格或不合格。 */}
              <div className="flex flex-wrap justify-around gap-2">
                <CalibrationGauge
                  label={t('enum.calibration.role_consistency')}
                  value={calibration.role_consistency?.average}
                  passLine={0.8}
                />
                <CalibrationGauge
                  label={t('enum.calibration.coverage')}
                  value={calibration.coverage?.average_distance}
                  passLine={0.3}
                />
                {calibration.hallucination != null && (
                  <CalibrationGauge
                    label={t('enum.calibration.hallucination')}
                    value={
                      calibration.hallucination.average == null ? null : 1 - calibration.hallucination.average
                    }
                  />
                )}
              </div>
              {calibration.overall_pass != null && (
                <p className={cn(
                  'mt-3 text-center text-xs font-medium',
                  calibration.overall_pass ? 'text-brand-primary' : 'text-warm-orange'
                )}>
                  {calibration.overall_pass
                    ? t('page.report.calibration.success')
                    : t('page.report.calibration.error')}
                </p>
              )}
            </>
          ) : (
            <p className="py-8 text-center text-xs text-text-muted">{t('page.report.calibration.empty')}</p>
          )}
        </div>
      </div>

      {/* ---------- 优先修复项 ---------- */}
      {priorityFixes.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-text-primary mb-4">{t('page.report.fixes.title')}</h3>
          <div className="flex flex-col gap-3">
            {priorityFixes.map((fix, index) => {
              const expanded = expandedIssues.has(index)
              const severity = VALID_SEVERITIES.includes(fix.severity as Severity)
                ? (fix.severity as Severity)
                : 'medium'
              return (
                <div key={index} className="rounded-xl border border-border bg-bg-card overflow-hidden">
                  <button
                    onClick={() => toggleIssue(index)}
                    className="w-full flex items-center gap-3 px-4 md:px-5 py-4 text-left hover:bg-bg-card-hover transition-colors"
                  >
                    <span className="font-mono text-xs text-text-muted shrink-0">#{fix.priority ?? index + 1}</span>
                    <SeverityBadge severity={severity} />
                    <span className="flex-1 text-sm font-medium text-text-primary">{fix.issue}</span>
                    {expanded ? (
                      <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                    )}
                  </button>
                  {expanded && (
                    <div className="px-4 md:px-5 pb-4 border-t border-border pt-3">
                      {fix.why_it_matters && (
                        <div className="mb-3">
                          <h4 className="text-xs font-medium text-text-muted mb-1">{t('page.report.fix_why.label')}</h4>
                          <p className="text-sm text-text-secondary">{fix.why_it_matters}</p>
                        </div>
                      )}
                      {fix.suggested_fix && (
                        <div className="mb-3">
                          <h4 className="text-xs font-medium text-text-muted mb-1">{t('page.report.fix_suggestion.label')}</h4>
                          <p className="text-sm text-text-secondary">{fix.suggested_fix}</p>
                        </div>
                      )}
                      {(fix.affected_personas?.length ?? 0) > 0 && (
                        <div>
                          <h4 className="text-xs font-medium text-text-muted mb-1.5">{t('page.report.fix_personas.label')}</h4>
                          <div className="flex flex-wrap gap-1.5">
                            {fix.affected_personas!.map((p) => (
                              <span key={p} className="px-2 py-0.5 rounded bg-bg-secondary text-xs text-text-secondary">
                                {p}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ---------- 人格视角 ---------- */}
      {personaNotes.length > 0 && (
        <div className="mb-6">
          <div className="mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-cyan" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">{t('page.report.personas.title')}</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {personaNotes.map((note) => {
              const stanceIndex = stanceData.findIndex((s) => s.name === noteStance(note))
              const stanceColor = STANCE_PALETTE[Math.max(stanceIndex, 0) % STANCE_PALETTE.length]
              const displayName = personaDisplayName(personaCatalog, note.persona_id, note.persona_name)
              return (
                <div key={note.persona_id} className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                  <div className="flex items-center gap-2.5 mb-3">
                    {/* 人格头像：与进度页同一套圆形身份标识，描边跟随立场色 */}
                    <div
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold"
                      style={{
                        borderColor: `${stanceColor}66`,
                        backgroundColor: `${stanceColor}1a`,
                        color: stanceColor,
                      }}
                    >
                      {displayName.slice(0, 1)}
                    </div>
                    <span className="font-medium text-text-primary">{displayName}</span>
                    <span className="text-xs text-text-muted font-mono">{note.persona_id}</span>
                    <span
                      className="ml-auto text-xs font-medium px-2 py-0.5 rounded"
                      style={{ backgroundColor: `${stanceColor}1a`, color: stanceColor }}
                    >
                      {noteStance(note)}
                    </span>
                  </div>

                  {(note.top_issues?.length ?? 0) > 0 && (
                    <div className="mb-2">
                      <h4 className="text-xs text-text-muted mb-1">{t('page.report.persona_issues.label')}</h4>
                      <ul className="space-y-0.5">
                        {note.top_issues!.map((issue, i) => (
                          <li key={i} className="text-xs text-text-secondary flex items-start gap-1.5">
                            <span className="text-warm-orange mt-0.5">•</span>
                            {issue}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {(note.evidence_top3?.length ?? 0) > 0 && (
                    <div>
                      <h4 className="text-xs text-text-muted mb-1">{t('page.report.persona_evidence.label')}</h4>
                      <ul className="space-y-0.5">
                        {note.evidence_top3!.map((e, i) => (
                          <li key={i} className="text-xs text-text-secondary flex items-start gap-1.5">
                            <span className="text-brand-primary mt-0.5">•</span>
                            {e}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ---------- 共识明细（引擎的 shared_concerns：谁提的、几人提的） ----------
          给出明细是让读者自己核对"这几条真是同一件事吗"，
          而不是只看执行摘要里一个光秃秃的计数 */}
      {(report.consensus?.shared_concerns?.length ?? 0) > 0 && (
        <div className="mb-6">
          <div className="mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-brand-primary" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">{t('page.report.consensus.title')}</h3>
            {typeof report.consensus?.min_personas_for_agreement === 'number' &&
              report.consensus.min_personas_for_agreement > 0 && (
                <span className="text-xs text-text-muted">
                  {t('page.report.consensus.hint', {
                    min: report.consensus.min_personas_for_agreement,
                    total: report.consensus.persona_count ?? '?',
                  })}
                </span>
              )}
          </div>
          <div className="flex flex-col gap-2">
            {report.consensus!.shared_concerns!.map((c, i) => (
              <div key={i} className="rounded-xl border border-border bg-bg-card p-3 md:p-4">
                <div className="flex items-start gap-2">
                  <span
                    className={cn(
                      'shrink-0 px-1.5 py-0.5 rounded text-xs font-medium',
                      c.is_consensus
                        ? 'bg-brand-primary/10 text-brand-primary'
                        : 'bg-bg-secondary text-text-muted'
                    )}
                  >
                    {c.is_consensus ? t('page.report.consensus.badge') : t('page.report.consensus_single.badge')}
                  </span>
                  <p className="text-sm text-text-primary min-w-0">{c.issue}</p>
                  <span className="ml-auto shrink-0 text-xs text-text-muted">
                    {/* 两个计数都没给就如实说没记录：写 0 会被读成"没人提过这条"，
                        而真相是这份报告没记录提出人数 */}
                    {(() => {
                      const raisers = c.persona_count ?? c.personas?.length
                      return typeof raisers === 'number'
                        ? t('page.report.consensus.meta', { count: raisers })
                        : t('page.report.consensus_unknown.meta')
                    })()}
                  </span>
                </div>
                {(c.personas?.length ?? 0) > 0 && (
                  <p className="mt-1.5 text-xs font-mono text-text-muted">
                    {c.personas!.join(t('page.report.sep_enum'))}
                  </p>
                )}
                {/* 合并了不同措辞时把原话列出来，读者才能核对聚类是否靠谱 */}
                {(c.title_variants?.length ?? 0) > 1 && (
                  <p className="mt-1 text-xs text-text-muted">
                    {t('page.report.consensus.desc', { variants: c.title_variants!.join(' / ') })}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---------- 主要分歧 ---------- */}
      {disagreements.length > 0 && (
        <div className="mb-6">
          <div className="mb-4 flex items-center gap-2">
            <Scale className="w-5 h-5 text-warm-orange" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">{t('page.report.disagreements.title')}</h3>
          </div>
          <div className="flex flex-col gap-3">
            {disagreements.map((d, i) => (
              <div key={i} className="overflow-x-auto rounded-xl border border-warm-orange/20 bg-bg-card p-4 md:p-5">
                <p className="text-sm font-medium text-text-primary mb-2">{d.topic}</p>
                {(d.persona_stances?.length ?? 0) > 0 && (
                  <ul className="space-y-1.5 mb-2">
                    {d.persona_stances!.map((ps, j) => (
                      <li key={j} className="text-xs text-text-secondary flex items-start gap-2">
                        <span className="shrink-0 font-mono text-text-muted">{ps.persona_id}</span>
                        <span className="shrink-0 px-1.5 rounded bg-bg-secondary text-text-primary">{ps.stance}</span>
                        <span>{ps.evidence}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {d.resolution_suggestion && (
                  <p className="text-xs text-text-muted">
                    {t('page.report.disagreement.hint', { text: d.resolution_suggestion })}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---------- 交叉质询（争议点 / 反驳 / 改票）---------- */}
      {crossExam ? <CrossExamSection view={crossExam} /> : <CrossExamAbsentNotice budget={report.budget} />}

      {/* ---------- 信息缺口 + 建议的下一步真人测试 ---------- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {informationGaps.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-border bg-bg-card p-4 md:p-5">
            <div className="mb-4 flex items-center gap-2">
              <HelpCircle className="w-4 h-4 text-warm-orange" strokeWidth={1.25} />
              <h3 className="text-sm font-semibold text-text-primary">{t('page.report.gaps.title')}</h3>
            </div>
            <ul className="space-y-2">
              {informationGaps.map((gap, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                  <span className="text-warm-orange font-display shrink-0">{i + 1}.</span>
                  {gap}
                </li>
              ))}
            </ul>
          </div>
        )}

        {report.next_human_test && (
          <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-4">{t('page.report.next_test.title')}</h3>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-xs text-text-muted mb-1">{t('page.report.next_test_tasks.label')}</dt>
                <dd className="text-text-secondary">
                  {(report.next_human_test.suggested_tasks ?? []).join(t('page.report.sep_semicolon')) || DASH}
                </dd>
              </div>
              <div>
                {/* 标题不能写"建议招募的人群"：recruit_types 是本次 AI 面板覆盖的
                    受众特征串（取自人格档案的真实属性），引擎并没有算"你该找谁"。
                    写成招募建议就是把没算过的东西说成算过了。 */}
                <dt className="text-xs text-text-muted mb-1">{t('page.report.next_test_audience.label')}</dt>
                <dd className="text-text-secondary">
                  {(report.next_human_test.recruit_types ?? []).join(t('page.report.sep_enum')) || DASH}
                </dd>
                {report.next_human_test.recruit_types_basis?.trim() && (
                  <p className="mt-1 text-xs text-text-muted">
                    {report.next_human_test.recruit_types_basis}
                  </p>
                )}
              </div>
              <div>
                <dt className="text-xs text-text-muted mb-1">{t('page.report.next_test_materials.label')}</dt>
                <dd className="text-text-secondary">
                  {(report.next_human_test.next_materials ?? []).join(t('page.report.sep_semicolon')) || DASH}
                </dd>
              </div>
            </dl>
          </div>
        )}
      </div>

      {/* ---------- 可证伪预测 ----------
           紧跟"下一步真人验证"：那一块说的是去做什么测试，
           这一块说的是测出什么结果算这次评审说对了。 */}
      <PredictionsSection predictions={report.predictions} />

      {/* ---------- 自适应面板轨迹 ---------- */}
      <AdaptivePanelSection adaptive={report.adaptive_panel} />

      {/* ---------- 伦理合规 ---------- */}
      {report.compliance && (
        <div className="mb-6 overflow-x-auto rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <div className="mb-4 flex items-center gap-2">
            <Shield className="w-4 h-4 text-purple-400" strokeWidth={1.25} />
            <h3 className="text-sm font-semibold text-text-primary">{t('page.report.compliance.title')}</h3>
            <span className={cn(
              'ml-auto text-xs px-2 py-0.5 rounded font-medium',
              (report.compliance.ethics_score ?? 0) >= 80
                ? 'bg-brand-primary/10 text-brand-primary'
                : (report.compliance.ethics_score ?? 0) >= 50
                  ? 'bg-severity-medium/10 text-severity-medium'
                  : 'bg-severity-critical/10 text-severity-critical'
            )}>
              {/* status 是引擎写的自由文本（"通过" / "需复核"…），原样透出不翻译 */}
              {t('page.report.compliance.badge', {
                status: report.compliance.status ?? DASH,
                score: report.compliance.ethics_score ?? DASH,
              })}
            </span>
          </div>
          {(report.compliance.recommended_steps?.length ?? 0) > 0 && (
            <ul className="space-y-1">
              {report.compliance.recommended_steps!.map((step, i) => (
                <li key={i} className="text-xs text-text-secondary flex items-start gap-1.5">
                  <span className="text-purple-400 mt-0.5">▸</span>
                  {step}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* ---------- 评估评分卡（独立端点，与 report_json 无关） ---------- */}
      {evaluationScorecard && (
        <div className="mb-6">
          <div className="mb-4 flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-cyan" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">{t('page.report.evaluation.title')}</h3>
          </div>

          {evaluationScorecard.critical_failures.length > 0 && (
            <div className="rounded-xl border-2 border-severity-critical/30 bg-severity-critical/5 p-4 md:p-5 mb-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertOctagon className="w-4 h-4 text-severity-critical" strokeWidth={1.25} />
                <h4 className="text-sm font-medium text-severity-critical">{t('page.report.evaluation_critical.title')}</h4>
              </div>
              <ul className="space-y-1">
                {evaluationScorecard.critical_failures.map((cf, i) => (
                  <li key={i} className="text-sm text-text-secondary flex items-start gap-1.5">
                    <span className="text-severity-critical mt-0.5">•</span>
                    {cf}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-4">
            <div className="overflow-x-auto rounded-xl border border-border bg-bg-card p-4 md:p-5">
              {/* 标出满分：右边那块维度分是 0–3，不写清楚两个数看起来是同一把尺子 */}
              <h4 className="text-sm font-medium text-text-muted mb-4">{t('page.report.evaluation_overall.label')}</h4>
              <div className="flex items-center gap-4">
                <div className={cn(
                  'w-20 h-20 rounded-full flex items-center justify-center border-4',
                  evaluationScorecard.overall_score > 70
                    ? 'border-brand-primary bg-brand-primary/10'
                    : evaluationScorecard.overall_score >= 50
                      ? 'border-severity-medium bg-severity-medium/10'
                      : 'border-severity-critical bg-severity-critical/10'
                )}>
                  <span className={cn(
                    'text-2xl font-bold font-mono',
                    evaluationScorecard.overall_score > 70
                      ? 'text-brand-primary'
                      : evaluationScorecard.overall_score >= 50
                        ? 'text-severity-medium'
                        : 'text-severity-critical'
                  )}>
                    {evaluationScorecard.overall_score}
                  </span>
                </div>
                <div>
                  <span className={cn(
                    'inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium',
                    evaluationScorecard.passed
                      ? 'bg-brand-primary/10 text-brand-primary'
                      : 'bg-severity-critical/10 text-severity-critical'
                  )}>
                    {evaluationScorecard.passed
                      ? <><CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.5} />{t('enum.verdict.pass')}</>
                      : <><XCircle className="w-3.5 h-3.5" strokeWidth={1.5} />{t('enum.verdict.fail')}</>}
                  </span>
                  <p className="text-xs text-text-muted mt-1">
                    {t('page.report.evaluation.meta', {
                      passed: evaluationScorecard.results.filter((r) => r.passed).length,
                      total: evaluationScorecard.results.length,
                    })}
                  </p>
                </div>
              </div>
            </div>

            <div className="overflow-x-auto rounded-xl border border-border bg-bg-card p-4 md:p-5">
              <h4 className="text-sm font-medium text-text-muted mb-4">{t('page.report.evaluation_dimension.label')}</h4>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={evaluationScorecard.results.map((r) => {
                  const dim = EVALUATION_DIMENSIONS.find((d) => d.id === r.dimension)
                  return {
                    name: dimensionLabel(r.dimension, dim?.name),
                    score: r.score,
                    fill: r.passed ? '#0071e3' : '#ff3355',
                  }
                })}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e5ea" />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#86868b' }} />
                  <YAxis domain={[0, DIMENSION_MAX_SCORE]} ticks={[0, 1, 2, 3]} tick={{ fontSize: 10, fill: '#86868b' }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1c1c1e', border: '1px solid #38383a', borderRadius: '12px', fontSize: '12px', boxShadow: '0 4px 16px rgba(0,0,0,0.3)' }}
                  itemStyle={{ color: '#ffffff' }}
                  />
                  <Bar dataKey="score" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {evaluationScorecard.results.map((result) => {
              const dim = EVALUATION_DIMENSIONS.find((d) => d.id === result.dimension)
              const expanded = expandedDimensions.has(result.dimension)
              return (
                <div key={result.dimension} className="rounded-xl border border-border bg-bg-card overflow-hidden">
                  <button
                    onClick={() => {
                      setExpandedDimensions((prev) => {
                        const next = new Set(prev)
                        if (next.has(result.dimension)) next.delete(result.dimension)
                        else next.add(result.dimension)
                        return next
                      })
                    }}
                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-bg-card-hover transition-colors"
                  >
                    <div className={cn(
                      'w-10 h-8 rounded-lg flex items-center justify-center text-xs font-bold font-mono',
                      result.passed ? 'bg-brand-primary/10 text-brand-primary' : 'bg-severity-critical/10 text-severity-critical'
                    )}>
                      {result.score}/{DIMENSION_MAX_SCORE}
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-text-primary">{dimensionLabel(result.dimension, dim?.name)}</span>
                      <span className={cn(
                        'ml-2 text-xs px-1.5 py-0.5 rounded',
                        result.passed ? 'bg-brand-primary/10 text-brand-primary' : 'bg-severity-critical/10 text-severity-critical'
                      )}>
                        {result.passed ? t('enum.verdict.pass') : t('enum.verdict.fail')}
                      </span>
                    </div>
                    {expanded ? (
                      <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                    ) : (
                      <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                    )}
                  </button>
                  {expanded && (
                    <div className="px-4 pb-3 border-t border-border pt-2">
                      {/* dim.description 来自 EVALUATION_DIMENSIONS（前端目录，
                          batch-0 的 catalog.eval_dimension 尚未交付），暂时仍是中文 */}
                      <p className="text-xs text-text-muted mb-1">
                        {dim?.description ?? t('page.report.evaluation_dimension.empty')}
                      </p>
                      <p className="text-sm text-text-secondary">{result.details}</p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* ---------- 伦理报告（独立端点） ---------- */}
      {ethicsReports.length > 0 && (
        <div className="mb-6">
          <div className="mb-4 flex items-center gap-2">
            <Shield className="w-5 h-5 text-purple-400" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">{t('page.report.ethics.title')}</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {ethicsReports.map((er) => (
              <div key={er.persona_id} className="overflow-x-auto rounded-xl border border-border bg-bg-card p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-text-primary">{er.persona_id}</span>
                  <span className={cn(
                    'inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded font-medium',
                    er.passed ? 'bg-brand-primary/10 text-brand-primary' : 'bg-severity-critical/10 text-severity-critical'
                  )}>
                    {er.passed
                      ? <><CheckCircle2 className="w-3 h-3" strokeWidth={1.5} />{t('enum.verdict.pass')}</>
                      : <><XCircle className="w-3 h-3" strokeWidth={1.5} />{t('enum.verdict.fail')}</>}
                  </span>
                </div>
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex-1">
                    <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                      <span>{t('page.report.ethics_score.label')}</span>
                      <span className={cn(
                        'font-mono font-bold',
                        er.score > 70 ? 'text-brand-primary' : er.score >= 50 ? 'text-severity-medium' : 'text-severity-critical'
                      )}>
                        {er.score}
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-bg-secondary overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          er.score > 70 ? 'bg-brand-primary' : er.score >= 50 ? 'bg-severity-medium' : 'bg-severity-critical'
                        )}
                        style={{ width: `${er.score}%` }}
                      />
                    </div>
                  </div>
                  {/* 刻板印象风险只有 low/medium/high 三档，没有百分比可言：
                      原来按 0–1 小数乘 100 显示，实际收到字符串，于是永远是
                      NaN% + 恒红「高风险」，进度条 width: NaN% 还是非法 CSS。 */}
                  <div className="flex-1">
                    <div className="text-xs text-text-muted mb-1">{t('page.report.ethics_stereotype.label')}</div>
                    <span className={cn(
                      'inline-block px-2 py-0.5 rounded text-xs font-medium',
                      stereotypeRiskBadgeClass(er.stereotype_risk)
                    )}>
                      {stereotypeRiskText(er.stereotype_risk)}
                    </span>
                  </div>
                </div>
                {er.violations.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-text-muted mb-1.5">
                      {t('page.report.ethics_violations.label', { count: er.violations.length })}
                    </h4>
                    <ul className="space-y-2">
                      {/* 后端给的是 {severity, rule, detail} 对象，老数据里还可能是
                          字符串——两种都在 toEthicsReportView 里收敛过了，这里
                          三个字段各自成列渲染，不会再把对象整个塞进 JSX。 */}
                      {er.violations.map((v, i) => (
                        <li
                          key={`${v.rule ?? 'legacy'}-${i}`}
                          className="rounded-lg border border-border bg-bg-secondary/50 px-2.5 py-2"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className={cn(
                              'px-1.5 py-0.5 rounded text-[10px] font-medium',
                              ETHICS_SEVERITY_BADGE_CLASSES[v.severity]
                            )}>
                              {t(ETHICS_SEVERITY_KEYS[v.severity])}
                            </span>
                            {v.rule && (
                              <code className="text-[10px] font-mono text-text-primary break-all">{v.rule}</code>
                            )}
                          </div>
                          <p className="text-xs text-text-secondary leading-relaxed">{v.detail}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---------- 评估操作区：运行评估 / 查看完整评估 / 失败说明收成一组，
          错误说明换行独占一行，不再和按钮挤在同一行里换行错位 ---------- */}
      <div className="mb-6 rounded-xl border border-border bg-bg-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <button
          onClick={async () => {
            if (!id) return
            setEvaluating(true)
            setEvaluationError(null)
            try {
              const result = await runEvaluation(id)
              setEvaluationScorecard(result)
            } catch (error) {
              // 以前这里是个空 catch：点完只看到转圈结束，既没有结果也没有原因，
              // 用户只能反复点。失败必须说出口。
              setEvaluationError(tApiError(error, 'page.report.evaluation.error'))
            } finally {
              setEvaluating(false)
            }
          }}
          disabled={evaluating}
          className={cn(
            'flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all',
            evaluating
              ? 'bg-bg-card text-text-muted cursor-not-allowed'
              : 'bg-cyan/10 text-cyan border border-cyan/30 hover:bg-cyan/20'
          )}
        >
          {evaluating ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} /> : <FlaskConical className="w-4 h-4" strokeWidth={1.25} />}
          {t('page.report.evaluation.cta')}
        </button>
        {evaluationScorecard && (
          <Link
            to={`/evaluations/${id}`}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm bg-purple-400/10 text-purple-400 border border-purple-400/30 hover:bg-purple-400/20 transition-all"
          >
            <FlaskConical className="w-4 h-4" strokeWidth={1.25} />
            {t('page.report.evaluation_full.cta')}
          </Link>
        )}
        </div>
        {evaluationError && (
          <p className="mt-3 flex items-start gap-1.5 text-sm text-severity-critical">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
            <span className="whitespace-pre-wrap break-words">
              {t('page.report.evaluation_run.error', { reason: evaluationError })}
            </span>
          </p>
        )}
      </div>

      {/* ---------- ETHICS.md 强制项：Limitations & Caveats ---------- */}
      <LimitationsSection caveats={report.meta?.caveats} />

      {/* ---------- 价值回填 ---------- */}
      {id && !feedbackSent && (
        <section className="mb-6 rounded-xl border border-brand-primary/30 bg-bg-card p-5">
          <h2 className="font-display text-sm font-semibold text-text-primary">{t('page.report.feedback.title')}</h2>
          <p className="mt-1 text-xs text-text-muted">{t('page.report.feedback.desc')}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className={cn('rounded-md border px-3 py-2 text-sm', feedbackUseful === true ? 'border-brand-primary bg-brand-primary/10 text-brand-primary' : 'border-border text-text-secondary')} onClick={() => setFeedbackUseful(true)}>{t('page.report.feedback_useful.cta')}</button>
            <button className={cn('rounded-md border px-3 py-2 text-sm', feedbackUseful === false ? 'border-severity-critical bg-severity-critical/10 text-severity-critical' : 'border-border text-text-secondary')} onClick={() => setFeedbackUseful(false)}>{t('page.report.feedback_useless.cta')}</button>
          </div>
          {feedbackUseful !== null && (
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              {priorityFixes.length > 0 && (
                <fieldset className="text-xs text-text-secondary sm:col-span-3">
                  <legend className="mb-2">{t('page.report.feedback_adopted.label')}</legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {priorityFixes.map((fix, i) => {
                      // title 同时是提交给后端的 adopted_fixes 元素。fix.issue 是
                      // 引擎原文，缺失时才用这条前端占位——它会跟着界面语言变，
                      // 而这只发生在"引擎没给标题"的情况下，不影响真实建议的可比性。
                      const title = fix.issue ?? t('page.report.feedback_fix.value', { index: i + 1 })
                      return (
                        <label key={i} className="flex items-start gap-2 rounded-md border border-border px-3 py-2">
                          <input type="checkbox" checked={adoptedFixes.includes(title)} onChange={(e) => setAdoptedFixes((current) => e.target.checked ? [...current, title] : current.filter((t) => t !== title))} className="mt-0.5 accent-brand-primary" />
                          <span>{title}</span>
                        </label>
                      )
                    })}
                  </div>
                </fieldset>
              )}
              <label className="text-xs text-text-secondary">{t('page.report.feedback_hours.label')}
                <input type="number" min={0} step="0.5" value={hoursSaved} onChange={(e) => setHoursSaved(Number(e.target.value))} className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 text-text-primary" />
              </label>
              <label className="text-xs text-text-secondary">{t('page.report.feedback_pay.label')}
                <input type="number" min={0} step="1" value={willingnessToPay} onChange={(e) => setWillingnessToPay(Number(e.target.value))} className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 text-text-primary" />
              </label>
              <label className="flex items-center gap-2 text-xs text-text-secondary sm:col-span-2">
                <input type="checkbox" checked={decisionChanged} onChange={(e) => setDecisionChanged(e.target.checked)} className="accent-brand-primary" />
                {t('page.report.feedback_decision.label')}
              </label>
              <button className="rounded-md bg-brand-primary px-4 py-2 text-sm font-semibold text-white" onClick={async () => {
                setFeedbackError(null)
                try {
                  await api.submitReviewFeedback(id, {
                    useful: feedbackUseful,
                    decision_changed: decisionChanged,
                    fixes_suggested: priorityFixes.length,
                    fixes_adopted: adoptedFixes.length,
                    adopted_fixes: adoptedFixes,
                    hours_saved: hoursSaved,
                    willingness_to_pay_usd: willingnessToPay,
                  })
                  setFeedbackSent(true)
                } catch (error) {
                  setFeedbackError(tApiError(error, 'page.report.feedback.error'))
                }
              }}>{t('page.report.feedback.cta')}</button>
            </div>
          )}
          {feedbackError && <p className="mt-3 text-xs text-severity-critical">{feedbackError}</p>}
        </section>
      )}
      {/* 引用的是导航项本身的译名（nav.item.ledger），不另写一份：
          导航改名时这句自动跟着改，不会出现"页面让我去某某页、导航里没这一项" */}
      {feedbackSent && (
        <p className="mb-6 text-sm text-brand-primary">
          {t('page.report.feedback.success', { section: t('nav.item.ledger') })}
        </p>
      )}
      </div>
    </div>
  )
}

// ---------- 匿名体验版 ----------

function GatedReportTeaser({ review, gated }: { review: Review | null; gated: RealReport }) {
  const summary = gated.executive_summary
  const fix = gated.priority_fixes?.[0]
  const fixesHidden = gated.gated_counts?.priority_fixes_hidden ?? 0
  const notesHidden = gated.gated_counts?.persona_notes_hidden ?? 0
  const gatedRiskKey = RISK_CONFIG[summary?.release_risk ?? '']?.labelKey

  return (
    <div className="max-w-3xl mx-auto px-4 py-10 animate-fade-in">
      {/* 体验版也是一份报告——ETHICS.md 的"每份报告必须"没有"匿名版除外"这一条 */}
      <SyntheticBanner />
      {gated.simulation_notice && (
        <div className="mb-4 rounded-xl border-2 border-severity-critical bg-severity-critical/10 p-4 text-sm font-bold text-severity-critical md:text-base">
          {gated.simulation_notice}
        </div>
      )}
      <DegradationNotice degradation={gated.degradation} />
      <SkillDegradedNotice notice={review?.skill_degraded} />

      <div className="flex items-center gap-3 mb-6">
        <Link to={review ? `/review/${review.id}` : '/'} className="p-2 rounded-lg hover:bg-bg-card transition-colors">
          <ArrowLeft className="w-5 h-5 text-text-secondary" strokeWidth={1.25} />
        </Link>
        <div>
          <h1 className="text-xl font-semibold text-text-primary">
            {review?.target_title ?? t('page.report.header.title')}
          </h1>
          <p className="text-sm text-text-secondary">{t('page.report.gated.subtitle')}</p>
        </div>
      </div>

      {summary && (
        <div className="rounded-xl border border-border bg-bg-card p-5 mb-4">
          <h2 className="text-sm font-medium text-text-muted mb-3">{t('page.report.gated_summary.title')}</h2>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-text-muted text-xs">{t('page.report.gated_risk.label')}</dt>
              <dd className="mt-1 font-medium text-text-primary">
                {gatedRiskKey
                  ? t(gatedRiskKey)
                  : summary.release_risk
                    ? t('page.report.unknown_level.value', { raw: summary.release_risk })
                    : DASH}
              </dd>
            </div>
            <div>
              <dt className="text-text-muted text-xs">{t('page.report.summary_evidence.label')}</dt>
              <dd className="mt-1 font-medium text-text-primary">
                {evidenceQualityLabel(summary.evidence_quality)}
              </dd>
            </div>
            {summary.primary_recommendation && (
              <div className="col-span-2 sm:col-span-3">
                <dt className="text-text-muted text-xs">{t('page.report.gated_recommendation.label')}</dt>
                <dd className="mt-1 font-medium text-text-primary">{summary.primary_recommendation}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {fix && (
        <div className="rounded-xl border border-border bg-bg-card p-5 mb-4">
          <h2 className="text-sm font-medium text-text-muted mb-3">{t('page.report.gated_fix.title')}</h2>
          <p className="font-medium text-text-primary">{fix.issue}</p>
          {fix.why_it_matters && <p className="mt-1 text-sm text-text-secondary">{fix.why_it_matters}</p>}
        </div>
      )}

      <div className="rounded-xl border border-brand-primary/30 bg-brand-primary/5 p-6 text-center">
        <Lock className="w-6 h-6 text-brand-primary mx-auto mb-3" strokeWidth={1.5} />
        <p className="text-text-primary font-medium">
          {t('page.report.gated.hint', { count: fixesHidden, notes: notesHidden })}
        </p>
        {/* 这句话必须和代码对得上。匿名评审落库时 user_id="anonymous"，登录后
            身份变了就再也打不开——所以"报告会保存在你的历史记录里"只有在认领
            链路真的存在时才成立（apiClient 的待认领清单 + POST
            /api/auth/me/claim-reviews）。认领靠的是这台浏览器本地记下的 id，
            所以"在这台设备上"不是废话，是这句承诺真实的边界。 */}
        <p className="mt-1 text-sm text-text-secondary">
          {t('page.report.gated.desc')}
        </p>
        <Link
          to="/login"
          className="mt-4 inline-block rounded-lg bg-brand-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors"
        >
          {t('page.report.gated.cta')}
        </Link>
      </div>

      <div className="mt-6">
        <LimitationsSection caveats={gated.meta?.caveats} />
      </div>
    </div>
  )
}

// ---------- 导出兜底（无服务端 markdown 时按真实字段现拼） ----------

/** 已知产出语言的显示名。认不出的 BCP-47 标签原样带出去——标签本身就是答案，
 *  比翻成一个我们猜的语种名诚实。 */
const REPORT_LANG_KEYS: Record<string, PlainMessageKey> = {
  'zh-CN': 'page.report.md_lang_zh.value',
  'en-US': 'page.report.md_lang_en.value',
}

/**
 * 导出件顶部那行"本报告正文语言"。契约 8.4 的强制项。
 *
 * 三个分支：认得的语种出译名；认不出的原样带标签；根本没有这个键就明说未记录。
 * **绝不把缺失当成中文**——那是在替一个从未被声明过的值作证（契约 D7）。
 */
function reportLanguageLine(language?: string): string {
  if (!language) return t('page.report.md_lang.empty')
  const key = REPORT_LANG_KEYS[language]
  return t('page.report.md_lang.value', { lang: key ? t(key) : language })
}

function generateMarkdown(report: RealReport): string {
  const lines: string[] = []
  const summary = report.executive_summary
  lines.push(`# ${t('page.report.header.title')}`)
  lines.push('')
  // 服务端的 markdown 走 src/templates/report-template.md，顶部自带 Synthetic Banner。
  // 这条兜底路径此前直接从"# 评审报告"开始，导出的文件里一句合成声明都没有。
  lines.push(`> **${t('page.report.synthetic_banner.title')}**`)
  lines.push(`> ${t('page.report.md_banner.desc')}`)
  lines.push('')
  // 契约 8.4：导出的是文件，脱离界面之后没人知道它是什么语言。
  // meta.language 只在引擎拿到真值时才写（aggregator 的"取得到真值才写这个键"），
  // 所以这里 null / undefined = **未记录**，不许当成中文（契约 D7）。
  lines.push(`> ${reportLanguageLine(report.meta?.language)}`)
  lines.push('')
  if (report.degradation?.degraded && report.degradation.notice) {
    lines.push(`> **⚠️ ${report.degradation.notice}**`)
    lines.push('')
  }
  // 导出件同样是"一份报告"：网页上置顶的两条坏消息（谁被校验拦下、
  // 有没有因为预算跳过环节）不能只存在于网页里
  const gatedOut = (report.validation?.gated_out ?? []).filter((g) => g.persona_id)
  if (gatedOut.length) {
    lines.push(`> **⚠️ ${t('page.report.md_gate.title', { count: gatedOut.length })}**`)
    for (const g of gatedOut) {
      lines.push(`> - ${g.persona_id}${t('page.report.sep_colon')}${gateReasonLabel(g.failure_reason)}`)
    }
    lines.push('')
  }
  if (report.budget?.exceeded) {
    const notice = report.budget.notice?.trim() || t('page.report.budget_generic.desc')
    lines.push(`> **⚠️ ${notice}**`)
    if ((report.budget.skipped_stages ?? []).includes('cross_examination')) {
      lines.push(`> ${t('page.report.md_budget.hint')}`)
    }
    lines.push('')
  }
  // 点名人格没全部参与也是坏消息之一，导出件里同样不能只字不提
  const panelNotice = report.panel_selection?.notice?.trim()
  if (panelNotice) {
    lines.push(`> **⚠️ ${panelNotice}**`)
    lines.push('')
  }
  if (summary) {
    const riskKey = RISK_CONFIG[summary.release_risk ?? '']?.labelKey
    const riskText = riskKey
      ? t(riskKey)
      : summary.release_risk
        ? t('page.report.unknown_level.value', { raw: summary.release_risk })
        : t('page.report.md_risk.empty')
    lines.push(`## ${t('page.report.md_risk.title', { risk: riskText })}`)
    lines.push('')
    lines.push(`- ${t('page.report.md_stance.label', { value: summary.primary_recommendation ?? DASH })}`)
    lines.push(`- ${t('page.report.md_evidence.label', { value: evidenceQualityLabel(summary.evidence_quality) })}`)
    lines.push('')
  }
  const fixes = report.priority_fixes ?? []
  if (fixes.length) {
    lines.push(`## ${t('page.report.fixes.title')}`)
    lines.push('')
    for (const fix of fixes) {
      // severity 在导出件里保持英文枚举大写：它是给人做 grep / 排序的标记，
      // 不是展示标签，翻了两份导出件就没法互相比对。
      lines.push(`### [${(fix.severity ?? 'medium').toUpperCase()}] ${fix.issue ?? ''}`)
      lines.push('')
      if (fix.why_it_matters) lines.push(fix.why_it_matters)
      if (fix.suggested_fix) {
        lines.push(`**${t('page.report.md_fix.label')}**${t('page.report.sep_colon')}${fix.suggested_fix}`)
      }
      lines.push('')
    }
  }
  // 交叉质询：这条兜底路径里也必须写清楚是三档里的哪一种。导出件同样是"一份报告"，
  // 少了这句话，读者只会按最强的那一档（多智能体反驳）理解。
  const crossExam = toCrossExamView(report.cross_examination)
  if (crossExam) {
    lines.push(`## ${t('page.report.cross_exam.title')}`)
    lines.push('')
    if (crossExam.is_legacy_array) {
      lines.push(t('page.report.md_cross_exam_legacy.desc'))
    } else {
      const label = crossExam.mode
        ? t(CROSS_EXAM_MODE_LABEL_KEYS[crossExam.mode])
        : crossExam.mode_raw
          ? t('page.report.cross_exam_mode_unknown.value', { raw: crossExam.mode_raw })
          : t('page.report.cross_exam_mode_unknown.label')
      lines.push(`- ${t('page.report.md_cross_exam.label', { mode: label })}`)
      const desc = crossExam.mode
        ? t(CROSS_EXAM_MODE_DESC_KEYS[crossExam.mode])
        : t('page.report.md_cross_exam.empty')
      lines.push(`- ${desc}`)
      // limitation 是引擎原文（产出物），只翻前缀不翻内容
      if (crossExam.limitation) {
        lines.push(`- ${t('page.report.md_cross_exam.hint', { text: crossExam.limitation })}`)
      }
      lines.push(
        crossExam.is_live_debate
          ? `- ${
              crossExam.vote_changes.length === 0
                ? t('page.report.md_vote_none.label', { count: 0 })
                : t('page.report.md_vote.label', { count: crossExam.vote_changes.length })
            }`
          : `- ${t('page.report.md_vote.empty')}`
      )
      if (crossExam.failures.length) {
        lines.push(
          `- ${t('page.report.md_failures.label', {
            count: crossExam.failures.length,
            list: crossExam.failures.map((f) => f.error).join(t('page.report.sep_semicolon')),
          })}`,
        )
      }
    }
    lines.push('')
  } else {
    // 整节缺席也要写出来：导出件里少一节，读者只会当"这次没什么争议"
    lines.push(`## ${t('page.report.cross_exam.title')}`)
    lines.push('')
    lines.push(
      report.budget?.exceeded && (report.budget.skipped_stages ?? []).includes('cross_examination')
        ? t('page.report.md_cross_exam_skipped.desc')
        : t('page.report.md_cross_exam_absent.desc')
    )
    lines.push('')
  }
  const gaps = report.information_gaps ?? []
  if (gaps.length) {
    lines.push(`## ${t('page.report.gaps.title')}`)
    lines.push('')
    gaps.forEach((g, i) => lines.push(`${i + 1}. ${g}`))
    lines.push('')
  }
  // ETHICS.md 要求每份报告都带 Limitations & Caveats——导出件同样算"一份报告"
  lines.push(`## ${t('page.report.limitations.title')}`)
  lines.push('')
  for (const item of [...(report.meta?.caveats ?? []), ...LIMITATION_KEYS.map((k) => t(k))]) {
    lines.push(`- ${item}`)
  }
  lines.push('')
  return lines.join('\n')
}
