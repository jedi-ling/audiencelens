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
} from '@/lib/mock-data'
import {
  EVALUATION_DIMENSIONS,
  ETHICS_SEVERITY_BADGE_CLASSES,
  ETHICS_SEVERITY_LABELS,
  CROSS_EXAM_MODE_LABELS,
  CROSS_EXAM_MODE_DESCRIPTIONS,
  REBUTTAL_STATUS_LABELS,
  REBUTTAL_STATUS_CLASSES,
  stereotypeRiskBadgeClass,
  stereotypeRiskLabel,
  toCrossExamView,
  toEthicsReportView,
} from '@/lib/mock-data'
import SeverityBadge from '@/components/SeverityBadge'
import CalibrationGauge from '@/components/CalibrationGauge'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import { ArrowLeft, ChevronDown, ChevronUp, AlertTriangle, Loader2, File, FileText, Globe, Shield, FlaskConical, AlertOctagon, Lock, Users, HelpCircle, Scale, Zap, ListChecks, Microscope, CheckCircle2, XCircle, Bot, Info, Swords, MessageSquareQuote, ArrowRightLeft, MinusCircle, TrendingUp, TrendingDown, Minus, RefreshCw, Share2, Copy } from 'lucide-react'

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
  is_gated?: boolean
  gated_counts?: { priority_fixes_hidden?: number; persona_notes_hidden?: number }
}

interface RealCalibration {
  role_consistency?: { average?: number } | null
  coverage?: { average_distance?: number } | null
  hallucination?: { average?: number } | null
  overall_pass?: boolean
}

// ---------- 展示映射 ----------

const RISK_CONFIG: Record<string, { label: string; color: string; bg: string; border: string }> = {
  low: { label: '低风险', color: 'text-brand-primary', bg: 'bg-brand-primary/10', border: 'border-brand-primary/30' },
  medium: { label: '中风险', color: 'text-severity-medium', bg: 'bg-severity-medium/10', border: 'border-severity-medium/30' },
  high: { label: '高风险', color: 'text-warm-orange', bg: 'bg-warm-orange/10', border: 'border-warm-orange/30' },
  critical: { label: '极高风险', color: 'text-severity-critical', bg: 'bg-severity-critical/10', border: 'border-severity-critical/30' },
}

/** release_risk 缺失/取值不认识时的显示。以前这里是 `?? RISK_CONFIG.medium`：
 *  报告里根本没有 executive_summary，页面照样打出"发布风险评估：中风险"——
 *  一个纯属编造的等级，而用户会拿它做发布决策。缺就显示「—」并说明缺了什么。 */
const UNKNOWN_RISK = { label: '—', color: 'text-text-muted', bg: 'bg-bg-card', border: 'border-border' }

const EVIDENCE_QUALITY_LABELS: Record<string, string> = {
  strong: '充分',
  medium: '中等',
  weak: '偏弱',
  insufficient: '不足',
}

// 立场是各任务类型自己的枚举（"加愿望单"/"值得推进"/"观望"…），无法穷举——按出现顺序配色
const STANCE_PALETTE = ['#0071e3', '#ff9f0a', '#ff6b35', '#ff3355', '#32ade6', '#a78bfa']

const MODE_BADGE: Record<ReviewMode, { label: string; color: string; bg: string; Icon: typeof Zap }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', Icon: Zap },
  standard: { label: '标准', color: 'text-brand-primary', bg: 'bg-brand-primary/10', Icon: ListChecks },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', Icon: Microscope },
}

const VALID_SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']

/** 评估记分卡的单维度满分。后端 evaluation_service.py 每个维度只产出 {0,1,2,3}，
 *  passed = score >= 2；只有 scorecard.overall_score 是 0–100。
 *  柱状图 Y 轴此前写死 0–100，于是满分 3 分的柱子恒定贴着地面，
 *  整块看起来像"每个维度都接近零分"。 */
const DIMENSION_MAX_SCORE = 3

/** 维度 id 不在本地词表里时明说不认识，不把 snake_case 当正常标题直出 */
function dimensionLabel(id: string, name?: string): string {
  return name ?? `${id}（未知维度）`
}

function noteStance(note: RealPersonaNote): string {
  return note.stance ?? note.primary_stance ?? '未表态'
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
            合成评审面板：以下全部意见由 AI 人格生成，不是真实玩家/用户的反馈。
          </p>
          <p className="mt-1.5 text-sm text-text-primary">
            本报告不得作为「玩家调研结果」「用户调查数据」「真实玩家意见分布」对外展示或引用。
            它是投入真人测试之前的预筛工具，不能替代真人 playtest 或用户访谈，也不应作为发布决策的唯一依据。
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
  const notice =
    degradation.notice?.trim() ||
    `本次有 ${degradation.failed_count ?? failed.length} 位人格未能完成评审，以下结论仅基于 ${degradation.succeeded_count ?? '部分'} 位人格的输出。`
  const failedLabels = failed.map((p) => p.persona_name || p.persona_id).filter(Boolean)
  return (
    <div className="mb-4 rounded-xl border-2 border-severity-critical bg-severity-critical/10 p-4">
      <div className="flex items-start gap-3">
        <AlertOctagon className="mt-0.5 h-5 w-5 shrink-0 text-severity-critical" strokeWidth={1.75} />
        <div>
          <p className="text-sm font-bold text-severity-critical md:text-base">{notice}</p>
          {failedLabels.length > 0 && (
            <p className="mt-1.5 text-sm text-text-primary">未完成的人格：{failedLabels.join('、')}</p>
          )}
        </div>
      </div>
    </div>
  )
}

/** 校验门控：这些人格跑出来了，但输出没过 schema / 角色一致性 / 证据核对，
 *  所以**不计入**下面任何结论。引擎只回传英文的失败类型枚举
 *  （src/runner/cli.py 的 RETRY_SCHEMA / RETRY_ROLE_DRIFT / RETRY_HALLUCINATION），
 *  这里逐条翻译；认不出的枚举原样显示，不猜、也不吞。 */
const GATE_REASON_LABELS: Record<string, string> = {
  schema_failure: '输出结构不合格（关键字段缺失或格式不对）',
  role_drift: '角色漂移（没有按这个人格的设定作答）',
  hallucination: '证据核对不通过（引用的原文在材料里找不到）',
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
            有 {gatedOut.length} 位人格的输出没通过质量校验，已被排除在下面的结论之外
          </p>
          <ul className="mt-2 space-y-1">
            {gatedOut.map((g, i) => (
              <li key={`${g.persona_id}-${i}`} className="text-sm text-text-primary">
                <span className="font-mono text-xs text-text-muted">{g.persona_id}</span>
                <span className="mx-1.5 text-text-muted">·</span>
                {g.failure_reason
                  ? GATE_REASON_LABELS[g.failure_reason] ?? `未知失败类型（${g.failure_reason}）`
                  : '引擎没有回传失败类型'}
              </li>
            ))}
          </ul>
        </div>
      </div>
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
          <p className="text-sm font-bold text-warm-orange">你点名的人格没有全部参与本次评审</p>
          <p className="mt-1.5 text-sm text-text-primary">{notice}</p>
          {(panelSelection?.matched ?? []).length > 0 && (
            <p className="mt-1.5 text-xs text-text-muted">
              实际参与：{(panelSelection?.matched ?? []).join('、')}
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
      ? `本次评审在人格环节已花费约 $${spent.toFixed(2)}，达到单次上限 $${cap.toFixed(2)}（budget.yaml 的 max_cost_per_run_usd）。`
      : '本次评审达到了单次成本上限。'
  const stages = budget.skipped_stages ?? []
  return (
    <div className="mb-4 rounded-xl border-2 border-warm-orange bg-warm-orange/10 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warm-orange" strokeWidth={1.75} />
        <div className="min-w-0">
          <p className="text-sm font-bold text-warm-orange md:text-base">
            成本达到单次上限，本次少跑了环节
          </p>
          <p className="mt-1.5 text-sm text-text-primary">{budget.notice?.trim() || fallback}</p>
          {stages.includes('cross_examination') && (
            <p className="mt-1.5 text-sm text-text-primary">
              交叉质询未执行。下面没有「交叉质询」这一节，不代表人格之间没有分歧，
              只代表这一轮没有跑辩论。
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
        <h3 className="text-lg font-semibold text-text-primary">交叉质询</h3>
      </div>
      <div className="rounded-xl border border-border bg-bg-secondary/40 p-4 text-sm text-text-secondary md:p-5">
        {skippedForCost ? (
          <p>
            本次没有执行交叉质询：人格环节的花费已达到单次成本上限，为免继续加钱而跳过（详见页面顶部的成本提示）。
            这不代表人格之间没有分歧，只代表这一轮没有跑辩论。
          </p>
        ) : (
          <p>
            这份报告里没有交叉质询记录。报告没有写明原因，可能是这一档评审模式不包含反驳环节，
            也可能是人格之间没有出现值得反驳的对立观点。请不要把它读成"大家意见一致"。
          </p>
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
 */
function reviewFailure(review: Review | null, report: RealReport | null): { reason: string | null } | null {
  const reason = failureDetail(report?.error)
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
            <h1 className="text-lg font-bold text-severity-critical md:text-xl">本次评审失败，没有生成报告</h1>
            <p className="mt-2 text-sm text-text-primary">
              这不是一份"没发现问题"的报告——评审没跑完，任何风险等级、共识点、立场分布都不存在。
              请不要据此做发布决策。
            </p>
            {review?.target_title && (
              <p className="mt-2 text-sm text-text-secondary">评审对象：{review.target_title}</p>
            )}
            <div className="mt-4 rounded-lg border border-severity-critical/40 bg-bg-card p-3">
              <p className="text-xs text-text-muted">失败原因（后端原文）</p>
              {reason ? (
                <p className="mt-1 whitespace-pre-wrap break-words font-mono text-xs text-text-primary">{reason}</p>
              ) : (
                <p className="mt-1 text-xs text-text-primary">
                  后端没有回传失败原因。评审详情页的角色执行记录里可能有更具体的报错。
                </p>
              )}
            </div>
            <div className="mt-4 flex flex-wrap gap-3">
              {reviewId && (
                <Link
                  to={`/review/${reviewId}`}
                  className="rounded-lg border border-border bg-bg-card px-4 py-2 text-sm text-text-secondary hover:border-brand-primary/30 hover:text-brand-primary transition-all"
                >
                  查看评审详情
                </Link>
              )}
              <Link
                to="/review/new"
                className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors"
              >
                重新发起评审
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
  return (
    <div className="max-w-3xl mx-auto px-4 py-10 animate-fade-in">
      <div className="rounded-xl border-2 border-warm-orange bg-warm-orange/10 p-5 md:p-6">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-6 w-6 shrink-0 text-warm-orange" strokeWidth={1.75} />
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-warm-orange md:text-xl">报告加载失败</h1>
            <p className="mt-2 text-sm text-text-primary">
              没能把这份报告取回来，所以下面什么都不显示——这不代表评审没有结果。
            </p>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm text-text-secondary">
              {error.message}
              {status !== null && status > 0 && <span className="ml-1 font-mono text-xs text-text-muted">HTTP {status}</span>}
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                onClick={onRetry}
                className="flex items-center gap-2 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors"
              >
                <RefreshCw className="h-4 w-4" strokeWidth={1.5} />
                重试
              </button>
              {needLogin && (
                <Link
                  to="/login"
                  className="rounded-lg border border-brand-primary/30 bg-bg-card px-4 py-2 text-sm text-brand-primary hover:bg-brand-primary/10 transition-colors"
                >
                  登录 / 注册
                </Link>
              )}
              {reviewId && (
                <Link
                  to={`/review/${reviewId}`}
                  className="rounded-lg border border-border bg-bg-card px-4 py-2 text-sm text-text-secondary hover:border-brand-primary/30 hover:text-brand-primary transition-all"
                >
                  查看评审详情
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
const LIMITATIONS: string[] = [
  '合成人格不是真人：立场分布反映的是 AI 人格的输出，不是任何真实用户群体的意见分布。',
  '过度一致性：LLM 模拟特定群体时输出方差通常低于真实人群，真实世界里的分歧可能被低估。',
  '材料决定质量：材料里缺少某类证据时人格会输出「未指定」，报告会标注信息缺口——「未指定」不等于「没有问题」。',
  'Demographic 不是因果解释：性别、年龄、地域本身不能解释偏好，不要据此把结论推广到某个真实人群。',
  '反馈循环风险：长期用同一套人格评审迭代版本，可能让产品过度迎合模拟出来的「平均偏好」，建议定期更换人格组合。',
]

/** ETHICS.md 强制项之二：Limitations & Caveats 章节（下载的 .md 一直有，网页端此前没有）。 */
export function LimitationsSection({ caveats }: { caveats?: string[] }) {
  const extra = (caveats ?? []).filter((c) => typeof c === 'string' && c.trim())
  return (
    <section className="mb-6 rounded-xl border border-warm-orange/40 bg-bg-card p-4 md:p-5">
      <div className="mb-3 flex items-center gap-2">
        <Info className="h-5 w-5 text-warm-orange" strokeWidth={1.5} />
        <h3 className="text-base font-semibold text-text-primary">局限与注意事项（Limitations &amp; Caveats）</h3>
      </div>
      <ul className="space-y-2">
        {[...extra, ...LIMITATIONS].map((item, i) => (
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
  pro: { label: '认为问题更严重', color: 'text-warm-orange', border: 'border-warm-orange/25' },
  con: { label: '认为问题更轻', color: 'text-cyan', border: 'border-cyan/25' },
} as const

/** 0–1 小数转百分比。null（读不出来）显示 "—"，绝不产出 "NaN%"——本仓库刚因为
 *  把三档字符串当小数乘 100 而满页 NaN%。 */
function confidencePct(value: number | null): string {
  return value === null ? '—' : `${Math.round(value * 100)}%`
}

/** confidence_changes 的 before/after 已经是百分点整数，不能再乘 100。 */
function pointPct(value: number | null): string {
  return value === null ? '—' : `${Math.round(value)}%`
}

/** 带正号的增量；null 显示 "—"。0 也照实显示成 0，不省略。 */
function signedNumber(value: number | null, digits: number): string {
  if (value === null) return '—'
  const fixed = Number(value.toFixed(digits))
  return `${fixed > 0 ? '+' : ''}${fixed}`
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
        <span className={cn('text-xs font-medium', meta.color)}>{meta.label}</span>
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
            这一方对对手论据的反驳
          </p>
          <p className="whitespace-pre-line text-xs text-text-secondary">{arg.rebuttal}</p>
        </div>
      ) : (
        // 只在真跑过反驳轮时才说"未产出反驳"；派生摘要档本来就没人反驳过，
        // 逐条写"未产出"只会让人以为这是一次失败。
        live && arg.argument_id && (
          <p className="mt-2 text-[11px] text-text-muted">这一方没有产出反驳。</p>
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
          {change.persona_name || change.persona_id || '未知人格'}
        </span>
        {change.argument_id && (
          <span className="rounded bg-bg-card px-1.5 font-mono text-xs text-text-muted">{change.argument_id}</span>
        )}
        {change.topic && <span className="text-xs text-text-muted">{change.topic}</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-bg-secondary px-1.5 py-0.5 text-text-secondary">{change.from_stance || '—'}</span>
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
          {accepted ? '' : '模型声称改为 '}
          {change.to_stance || '—'}
        </span>
      </div>
      <p className="mt-1.5 text-xs text-text-muted">
        置信度 {confidencePct(change.confidence_before)} → {confidencePct(change.confidence_after)}
        （变化 {signedNumber(change.delta, 2)}
        {threshold !== null && `，采纳阈值 θ=${threshold}`}）
      </p>
      {!accepted && change.suppressed_reason && (
        <p className="mt-1.5 text-xs text-severity-medium">未采纳原因：{change.suppressed_reason}</p>
      )}
      {change.reason && (
        <p className="mt-1.5 whitespace-pre-line text-xs text-text-secondary">依据（反驳原文）：{change.reason}</p>
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
          <h3 className="text-lg font-semibold text-text-primary">交叉质询</h3>
        </div>
        <div className="rounded-xl border border-border bg-bg-card p-4 text-sm text-text-secondary md:p-5">
          这份报告由旧版本生成，交叉质询记录以旧格式保存（{view.legacy_entry_count} 条原始条目），
          无法解析出争议点、反驳内容与改票明细。重新发起一次评审即可得到完整记录。
        </div>
      </div>
    )
  }

  const live = view.is_live_debate
  const modeLabel = view.mode ? CROSS_EXAM_MODE_LABELS[view.mode] : `未知模式${view.mode_raw ? `（${view.mode_raw}）` : ''}`
  const modeBadgeClass = view.mode ? CROSS_EXAM_MODE_BADGE[view.mode] : 'bg-severity-medium/10 text-severity-medium border-severity-medium/30'
  const modeDescription = view.mode
    ? CROSS_EXAM_MODE_DESCRIPTIONS[view.mode]
    : '这份报告没有标明交叉质询的执行方式，无法判断是否真的发生过反驳——请按"未发生反驳"理解。'
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
        <h3 className="text-lg font-semibold text-text-primary">交叉质询</h3>
        <span className={cn('rounded border px-2 py-0.5 text-xs font-medium', modeBadgeClass)}>{modeLabel}</span>
        {live && view.rounds_run > 0 && (
          <span className="text-xs text-text-muted">实际执行 {view.rounds_run} 轮</span>
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
            本次请求的是「{view.requested_mode ? CROSS_EXAM_MODE_LABELS[view.requested_mode] : view.requested_mode_raw}」，
            实际回落为「{modeLabel}」。
          </p>
        )}
        {view.limitation && limitationTone === 'muted' && (
          <p className="mt-2 text-xs text-text-muted">引擎原始说明：{renderEmphasis(view.limitation)}</p>
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
              交叉质询过程中的失败（{view.failures.length} 条）
            </h4>
          </div>
          <ul className="space-y-1">
            {view.failures.map((f, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-1.5 text-xs text-text-secondary">
                <span className="rounded bg-bg-secondary px-1.5 font-mono text-text-muted">
                  {[f.stage, f.point_id, f.argument_id].filter(Boolean).join(' · ') || '未标注阶段'}
                </span>
                <span>{f.error || '未给出原因'}</span>
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
                <p className="flex-1 text-sm font-medium text-text-primary">{d.topic || '未命名争议点'}</p>
                <span className={cn('rounded px-2 py-0.5 text-xs font-medium', REBUTTAL_STATUS_CLASSES[d.rebuttal_status])}>
                  {REBUTTAL_STATUS_LABELS[d.rebuttal_status]}
                </span>
              </div>
              {d.rebuttal_status !== 'ok' && d.rebuttal_error && (
                <p className="mb-3 text-xs text-severity-medium">本争议点交叉质询未完成：{d.rebuttal_error}</p>
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
            ? '本次没有找到需要质询的争议点——各人格在关键判断上没有出现足够大的分歧。'
            : '本次没有产出可展示的争议点，原因见上方说明。'}
        </div>
      )}

      {/* 改票记录。"没有人改票"是正常结果，必须写出来而不是留空白。 */}
      <div className="mb-3 rounded-xl border border-border bg-bg-card p-4 md:p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <ArrowRightLeft className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
          <h4 className="text-sm font-semibold text-text-primary">改票记录</h4>
          {live && (
            <span className="text-xs text-text-muted">
              {view.vote_changes.length} 条
              {view.threshold !== null && ` · 采纳阈值 θ=${view.threshold}`}
            </span>
          )}
        </div>
        {!live ? (
          <p className="text-sm text-text-secondary">
            本次未进行反驳轮，因此不存在改票记录。改票只能来自真实发生过的反驳。
          </p>
        ) : view.vote_changes.length === 0 ? (
          <p className="text-sm text-text-secondary">
            本轮双方立场未变。这是交叉质询中完全正常、而且常见的结果，不代表反驳没有发生。
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
              另有 {view.suppressed_changes.length} 条立场变化由模型提出、但未被采纳
              （改票由代码判定，不采信模型自报）
              {!view.allow_stance_update && '；本次配置为不接受立场更新'}
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
          <h4 className="mb-3 text-sm font-semibold text-text-primary">反驳前后的置信度</h4>
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
                  <span className="min-w-24 text-text-primary">{cc.persona_id || cc.persona_key || '未知人格'}</span>
                  <span className="text-text-secondary">
                    {pointPct(cc.before)} → {pointPct(cc.after)}
                  </span>
                  <span className={cn('flex items-center gap-1', deltaClass)}>
                    <Icon className="h-3 w-3" strokeWidth={1.5} />
                    {delta === null ? '—' : `${signedNumber(delta, 0)} 个百分点`}
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
          本节发起 {view.usage.calls} 次模型调用（含失败的尝试）· 输入 {view.usage.input_tokens.toLocaleString()} tokens ·
          输出 {view.usage.output_tokens.toLocaleString()} tokens
          {!view.usage.token_counts_available && '（token 用量未被完整回报，实际成本可能高于账面）'}
        </p>
      )}

      {/* θ 没读到配置、走了内置默认值时才提——正常读到 yaml 时展示文件路径只是噪音 */}
      {view.threshold_source.startsWith('fallback-default') && (
        <p className="mt-1 text-xs text-severity-medium">
          改票阈值未能从配置读取，本次使用内置默认值（{view.threshold_source}）。
        </p>
      )}
    </div>
  )
}

export default function ReportPage() {
  const { id } = useParams()
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
      setShareError(e instanceof Error ? e.message : '生成分享链接失败')
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
      setShareError(e instanceof Error ? e.message : '撤销失败')
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
      setShareError('浏览器拒绝了剪贴板访问，请手动选中上面的链接复制')
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
            withError.html_error?.trim() || '后端没有回传这份报告的 HTML 版本（也没有说明原因）。'
          )
        }
        if (result.report_md && !reportMarkdown) setReportMarkdown(result.report_md)
      })
      .catch((error: unknown) => {
        setHtmlUnavailable(
          `取 HTML 版本失败：${error instanceof Error ? error.message : String(error)}`
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
        <p className="text-text-secondary">加载报告中...</p>
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
        <p className="text-text-secondary">报告尚未生成</p>
        <p className="mt-2 text-sm text-text-muted">评审可能还在跑，也可能还没开始——去详情页看实时进度。</p>
        <Link to={`/review/${id}`} className="text-cyan hover:text-cyan-dim mt-4 inline-block">查看进度</Link>
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
    <div className="max-w-6xl mx-auto px-4 py-6 animate-fade-in">
      {/* 三条诚实信号一律置顶，不滚动就能看到：合成声明（ETHICS.md 强制）、
          模拟占位输出、人格降级。它们比报告结论本身更需要被先看到。 */}
      <SyntheticBanner />
      {report.simulation_notice && (
        <div className="mb-4 rounded-xl border-2 border-severity-critical bg-severity-critical/10 p-4 text-sm font-bold text-severity-critical md:text-base">
          {report.simulation_notice}
        </div>
      )}
      <DegradationNotice degradation={report.degradation} />
      <ValidationGateNotice validation={report.validation} />
      <BudgetNotice budget={report.budget} />
      <PanelSelectionNotice panelSelection={report.panel_selection} />

      <div className="flex items-center gap-3 mb-6">
        <Link to={`/review/${id}`} className="p-2 rounded-lg hover:bg-bg-card transition-colors">
          <ArrowLeft className="w-5 h-5 text-text-secondary" strokeWidth={1.25} />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold text-text-primary truncate">
            {review.target_title || report.meta?.target || '评审报告'}
          </h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-text-secondary">评审报告</p>
            <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', modeBadge.bg, modeBadge.color)}>
              <modeBadge.Icon className="w-3 h-3" strokeWidth={1.5} />
              {modeBadge.label}模式
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setSharePanelOpen((v) => !v)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm transition-all',
              shareToken
                ? 'bg-brand-primary/10 border-brand-primary/30 text-brand-primary'
                : 'bg-bg-card border-border text-text-secondary hover:border-brand-primary/30 hover:text-brand-primary'
            )}
          >
            <Share2 className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">{shareToken ? '已公开' : '分享'}</span>
          </button>
          <button
            onClick={() => handleExport('json')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card border border-border text-sm text-text-secondary hover:border-brand-primary/30 hover:text-brand-primary transition-all"
          >
            <File className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">JSON</span>
          </button>
          <button
            onClick={() => handleExport('markdown')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card border border-border text-sm text-text-secondary hover:border-cyan/30 hover:text-cyan transition-all"
          >
            <FileText className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">MD</span>
          </button>
          <button
            onClick={() => handleExport('html')}
            disabled={!reportHtml}
            title={reportHtml ? undefined : htmlUnavailable ?? 'HTML 版本还在生成中'}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm transition-all',
              reportHtml
                ? 'bg-bg-card border-border text-text-secondary hover:border-warm-orange/30 hover:text-warm-orange'
                : 'bg-bg-secondary border-border text-text-muted cursor-not-allowed'
            )}
          >
            <Globe className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">HTML</span>
          </button>
        </div>
      </div>

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
              <h3 className="text-sm font-semibold text-text-primary">只读分享链接</h3>
              <p className="mt-1 text-xs text-text-secondary">
                生成一条链接发给合伙人或团队，<strong className="text-text-primary">对方无需注册即可打开</strong>。
                任何拿到链接的人都能看，所以别发到公开场合。
              </p>

              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-border bg-bg-secondary/50 p-3">
                  <div className="text-[11px] font-semibold text-text-secondary mb-1.5">对方能看到</div>
                  <ul className="space-y-1 text-[11px] text-text-muted">
                    <li>· 报告全文（摘要、优先修复、各角色视角、共识与分歧）</li>
                    <li>· 这次评审的标题与任务类型</li>
                    <li>· 评审时间与校准指标</li>
                  </ul>
                </div>
                <div className="rounded-lg border border-border bg-bg-secondary/50 p-3">
                  <div className="text-[11px] font-semibold text-text-secondary mb-1.5">对方看不到</div>
                  <ul className="space-y-1 text-[11px] text-text-muted">
                    <li>· 你的账号与邮箱</li>
                    <li>· 这次评审的花费与 token 消耗</li>
                    <li>· 你上传的原始材料</li>
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
                      aria-label="分享链接"
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
                      {shareCopied ? '已复制' : '复制'}
                    </button>
                    <button
                      onClick={() => void handleUnshare()}
                      disabled={shareBusy}
                      className="flex items-center gap-1.5 rounded-md border border-severity-critical/30 bg-severity-critical/5 px-3 py-2 text-xs text-severity-critical transition-colors hover:bg-severity-critical/10 disabled:opacity-50"
                    >
                      {shareBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} /> : <Lock className="h-3.5 w-3.5" strokeWidth={1.5} />}
                      撤销
                    </button>
                  </div>
                  <p className="mt-2 text-[11px] text-text-muted">
                    撤销后这条链接立刻失效，已经打开过的人也无法再次访问。再次分享会生成一条新链接。
                  </p>
                </div>
              ) : (
                <button
                  onClick={() => void handleShare()}
                  disabled={shareBusy}
                  className="mt-4 flex items-center gap-1.5 rounded-md bg-brand-primary px-4 py-2 text-xs font-semibold text-white transition-colors hover:bg-brand-primary-dim disabled:opacity-50"
                >
                  {shareBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} /> : <Share2 className="h-3.5 w-3.5" strokeWidth={1.5} />}
                  生成分享链接
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
            这份报告没有 HTML 可视化版本：{htmlUnavailable}
            上面的网页内容和 JSON / Markdown 导出不受影响。
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
              HTML 可视化报告
            </span>
            {showHtmlReport
              ? <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
              : <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
            }
          </button>
          {showHtmlReport && (
            <div className="mt-3 rounded-xl border border-border overflow-hidden bg-bg-card">
              <iframe
                ref={iframeRef}
                title="HTML Report"
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
            发布风险评估：{riskView.label}
          </h2>
        </div>
        {/* 缺等级要说是"报告没给"，不是"评估结果是中风险" */}
        {!risk && (
          <p className="mb-3 text-xs text-text-muted">
            这份报告没有给出发布风险等级
            {summary?.release_risk ? `（收到的取值「${summary.release_risk}」不在已知档位里）` : '（执行摘要里没有 release_risk）'}
            ，这里不替它推断。
          </p>
        )}
        <dl className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <div>
            <dt className="text-xs text-text-muted">评审团主流立场</dt>
            <dd className="mt-1 font-medium text-text-primary">{summary?.primary_recommendation || '—'}</dd>
          </div>
          <div>
            <dt className="text-xs text-text-muted">证据充分度</dt>
            <dd className="mt-1 font-medium text-text-primary">
              {EVIDENCE_QUALITY_LABELS[summary?.evidence_quality ?? ''] ?? summary?.evidence_quality ?? '—'}
            </dd>
          </div>
          <div>
            {/* 口径跟 aggregator.compute_consensus 的 docstring 对齐：
                agreed_points = 至少两位人格各自提到的同一议题；
                questioned_points = 只有个别人格提出的关切，不是"大家共同质疑"。
                写成"存疑点"会被读反。 */}
            <dt className="text-xs text-text-muted">共识议题 / 个别人格单独提出</dt>
            {/* 报告压根没有 consensus 区块时显示「—」：0/0 会被读成"跑过了、没找到共识问题"，
                和"这一节根本没产出"是两回事 */}
            <dd className="mt-1 font-medium text-text-primary">
              {report.consensus
                ? `${report.consensus.agreed_points?.length ?? 0} / ${report.consensus.questioned_points?.length ?? 0}`
                : '—'}
            </dd>
            {/* 判定口径来自引擎的 min_personas_for_agreement，不在前端重算——
                引擎改阈值时这里自动跟着变，两套口径并存正是要避免的坑 */}
            {typeof report.consensus?.min_personas_for_agreement === 'number' &&
              report.consensus.min_personas_for_agreement > 0 && (
                <p className="mt-0.5 text-xs text-text-muted">
                  判定口径：同一议题被 ≥{report.consensus.min_personas_for_agreement}/
                  {report.consensus.persona_count ?? '?'} 位人格各自独立提出
                </p>
              )}
          </div>
        </dl>
      </div>

      {/* ---------- 立场分布 + 校准指标 ---------- */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <h3 className="text-sm font-medium text-text-muted mb-4">立场分布（{personaNotes.length} 个人格）</h3>
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
            <p className="py-8 text-center text-xs text-text-muted">暂无人格立场数据</p>
          )}
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <h3 className="text-sm font-medium text-text-muted mb-4">校准指标</h3>
          {calibration ? (
            <>
              {/* 合格线全部来自 src/runner/calibration.py::run_calibration_check：
                  overall_pass = role_consistency.average >= 0.8 且 coverage.average_distance >= 0.3。
                  无幻觉率**没有**参与 overall_pass，引擎里只有"单个人格幻觉率 > 0.5 记为高风险"
                  这一条，跟这里的平均值不是同一个量，所以不给它安合格线——
                  给一条编出来的线，就等于凭空判一个指标合格或不合格。 */}
              <div className="flex flex-wrap justify-around gap-2">
                <CalibrationGauge
                  label="角色一致性"
                  value={calibration.role_consistency?.average}
                  passLine={0.8}
                />
                <CalibrationGauge
                  label="视角覆盖度"
                  value={calibration.coverage?.average_distance}
                  passLine={0.3}
                />
                {calibration.hallucination != null && (
                  <CalibrationGauge
                    label="无幻觉率"
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
                  {calibration.overall_pass ? '校准通过' : '校准未达标——结论请谨慎采信'}
                </p>
              )}
            </>
          ) : (
            <p className="py-8 text-center text-xs text-text-muted">本次评审未运行校准检查</p>
          )}
        </div>
      </div>

      {/* ---------- 优先修复项 ---------- */}
      {priorityFixes.length > 0 && (
        <div className="mb-6">
          <h3 className="text-lg font-semibold text-text-primary mb-4">优先修复项</h3>
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
                          <h4 className="text-xs font-medium text-text-muted mb-1">为什么重要</h4>
                          <p className="text-sm text-text-secondary">{fix.why_it_matters}</p>
                        </div>
                      )}
                      {fix.suggested_fix && (
                        <div className="mb-3">
                          <h4 className="text-xs font-medium text-text-muted mb-1">修复建议</h4>
                          <p className="text-sm text-text-secondary">{fix.suggested_fix}</p>
                        </div>
                      )}
                      {(fix.affected_personas?.length ?? 0) > 0 && (
                        <div>
                          <h4 className="text-xs font-medium text-text-muted mb-1.5">提出的人格</h4>
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
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-5 h-5 text-cyan" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">人格视角</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {personaNotes.map((note) => {
              const stanceIndex = stanceData.findIndex((s) => s.name === noteStance(note))
              const stanceColor = STANCE_PALETTE[Math.max(stanceIndex, 0) % STANCE_PALETTE.length]
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
                      {(note.persona_name ?? note.persona_id).slice(0, 1)}
                    </div>
                    <span className="font-medium text-text-primary">{note.persona_name ?? note.persona_id}</span>
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
                      <h4 className="text-xs text-text-muted mb-1">关键议题</h4>
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
                      <h4 className="text-xs text-text-muted mb-1">关键证据</h4>
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
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-5 h-5 text-brand-primary" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">议题共识明细</h3>
            {typeof report.consensus?.min_personas_for_agreement === 'number' &&
              report.consensus.min_personas_for_agreement > 0 && (
                <span className="text-xs text-text-muted">
                  共识 = 同一议题被 ≥{report.consensus.min_personas_for_agreement}/
                  {report.consensus.persona_count ?? '?'} 位人格各自独立提出
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
                    {c.is_consensus ? '共识' : '个别提出'}
                  </span>
                  <p className="text-sm text-text-primary min-w-0">{c.issue}</p>
                  <span className="ml-auto shrink-0 text-xs text-text-muted">
                    {c.persona_count ?? c.personas?.length ?? '?'} 人提出
                  </span>
                </div>
                {(c.personas?.length ?? 0) > 0 && (
                  <p className="mt-1.5 text-xs font-mono text-text-muted">
                    {c.personas!.join('、')}
                  </p>
                )}
                {/* 合并了不同措辞时把原话列出来，读者才能核对聚类是否靠谱 */}
                {(c.title_variants?.length ?? 0) > 1 && (
                  <p className="mt-1 text-xs text-text-muted">
                    合并的措辞：{c.title_variants!.join(' / ')}
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
          <div className="flex items-center gap-2 mb-4">
            <Scale className="w-5 h-5 text-warm-orange" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">主要分歧</h3>
          </div>
          <div className="flex flex-col gap-3">
            {disagreements.map((d, i) => (
              <div key={i} className="rounded-xl border border-warm-orange/20 bg-bg-card p-4 md:p-5">
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
                  <p className="text-xs text-text-muted">建议：{d.resolution_suggestion}</p>
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
          <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
            <div className="flex items-center gap-2 mb-4">
              <HelpCircle className="w-4 h-4 text-warm-orange" strokeWidth={1.25} />
              <h3 className="text-sm font-semibold text-text-primary">信息缺口</h3>
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
            <h3 className="text-sm font-semibold text-text-primary mb-4">建议的下一步真人验证</h3>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-xs text-text-muted mb-1">验证任务</dt>
                <dd className="text-text-secondary">
                  {(report.next_human_test.suggested_tasks ?? []).join('；') || '—'}
                </dd>
              </div>
              <div>
                {/* 标题不能写"建议招募的人群"：recruit_types 是本次 AI 面板覆盖的
                    受众特征串（取自人格档案的真实属性），引擎并没有算"你该找谁"。
                    写成招募建议就是把没算过的东西说成算过了。 */}
                <dt className="text-xs text-text-muted mb-1">本次面板覆盖的受众特征</dt>
                <dd className="text-text-secondary">
                  {(report.next_human_test.recruit_types ?? []).join('、') || '—'}
                </dd>
                {report.next_human_test.recruit_types_basis?.trim() && (
                  <p className="mt-1 text-xs text-text-muted">
                    {report.next_human_test.recruit_types_basis}
                  </p>
                )}
              </div>
              <div>
                <dt className="text-xs text-text-muted mb-1">需要补充的材料</dt>
                <dd className="text-text-secondary">
                  {(report.next_human_test.next_materials ?? []).join('；') || '—'}
                </dd>
              </div>
            </dl>
          </div>
        )}
      </div>

      {/* ---------- 伦理合规 ---------- */}
      {report.compliance && (
        <div className="mb-6 rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-purple-400" strokeWidth={1.25} />
            <h3 className="text-sm font-semibold text-text-primary">人格伦理合规</h3>
            <span className={cn(
              'ml-auto text-xs px-2 py-0.5 rounded font-medium',
              (report.compliance.ethics_score ?? 0) >= 80
                ? 'bg-brand-primary/10 text-brand-primary'
                : (report.compliance.ethics_score ?? 0) >= 50
                  ? 'bg-severity-medium/10 text-severity-medium'
                  : 'bg-severity-critical/10 text-severity-critical'
            )}>
              {report.compliance.status ?? '—'} · {report.compliance.ethics_score ?? '—'} 分
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
          <div className="flex items-center gap-2 mb-4">
            <FlaskConical className="w-5 h-5 text-cyan" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">评估评分卡</h3>
          </div>

          {evaluationScorecard.critical_failures.length > 0 && (
            <div className="rounded-xl border-2 border-severity-critical/30 bg-severity-critical/5 p-4 md:p-5 mb-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertOctagon className="w-4 h-4 text-severity-critical" strokeWidth={1.25} />
                <h4 className="text-sm font-medium text-severity-critical">关键失败项</h4>
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
            <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
              {/* 标出满分：右边那块维度分是 0–3，不写清楚两个数看起来是同一把尺子 */}
              <h4 className="text-sm font-medium text-text-muted mb-4">总体评分（满分 100）</h4>
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
                      ? <><CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.5} />通过</>
                      : <><XCircle className="w-3.5 h-3.5" strokeWidth={1.5} />未通过</>}
                  </span>
                  <p className="text-xs text-text-muted mt-1">
                    {evaluationScorecard.results.filter((r) => r.passed).length}/{evaluationScorecard.results.length} 维度通过
                  </p>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
              <h4 className="text-sm font-medium text-text-muted mb-4">维度评分（每项满分 3，合格线 2）</h4>
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
                        {result.passed ? '通过' : '未通过'}
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
                      <p className="text-xs text-text-muted mb-1">{dim?.description ?? '本地词表里没有这个维度的说明'}</p>
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
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-purple-400" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">伦理报告</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {ethicsReports.map((er) => (
              <div key={er.persona_id} className="rounded-xl border border-border bg-bg-card p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-text-primary">{er.persona_id}</span>
                  <span className={cn(
                    'inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded font-medium',
                    er.passed ? 'bg-brand-primary/10 text-brand-primary' : 'bg-severity-critical/10 text-severity-critical'
                  )}>
                    {er.passed
                      ? <><CheckCircle2 className="w-3 h-3" strokeWidth={1.5} />通过</>
                      : <><XCircle className="w-3 h-3" strokeWidth={1.5} />未通过</>}
                  </span>
                </div>
                <div className="flex items-center gap-3 mb-3">
                  <div className="flex-1">
                    <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                      <span>伦理评分</span>
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
                    <div className="text-xs text-text-muted mb-1">刻板印象风险</div>
                    <span className={cn(
                      'inline-block px-2 py-0.5 rounded text-xs font-medium',
                      stereotypeRiskBadgeClass(er.stereotype_risk)
                    )}>
                      {stereotypeRiskLabel(er.stereotype_risk)}
                    </span>
                  </div>
                </div>
                {er.violations.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-text-muted mb-1.5">违规项 {er.violations.length}</h4>
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
                              {ETHICS_SEVERITY_LABELS[v.severity]}
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

      <div className="flex flex-wrap items-center gap-3 mb-6">
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
              setEvaluationError(error instanceof Error ? error.message : '运行质量评估失败')
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
          运行评估
        </button>
        {evaluationScorecard && (
          <Link
            to={`/evaluations/${id}`}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm bg-purple-400/10 text-purple-400 border border-purple-400/30 hover:bg-purple-400/20 transition-all"
          >
            <FlaskConical className="w-4 h-4" strokeWidth={1.25} />
            查看完整评估
          </Link>
        )}
        {evaluationError && (
          <p className="flex items-start gap-1.5 text-sm text-severity-critical">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={1.5} />
            <span className="whitespace-pre-wrap break-words">运行评估失败：{evaluationError}</span>
          </p>
        )}
      </div>

      {/* ---------- ETHICS.md 强制项：Limitations & Caveats ---------- */}
      <LimitationsSection caveats={report.meta?.caveats} />

      {/* ---------- 价值回填 ---------- */}
      {id && !feedbackSent && (
        <section className="mb-6 rounded-xl border border-brand-primary/30 bg-bg-card p-5">
          <h2 className="font-display text-sm font-semibold text-text-primary">这份报告真的有用吗？</h2>
          <p className="mt-1 text-xs text-text-muted">反馈将用于衡量建议采纳与决策影响，不用调用次数冒充价值。</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className={cn('rounded-md border px-3 py-2 text-sm', feedbackUseful === true ? 'border-brand-primary bg-brand-primary/10 text-brand-primary' : 'border-border text-text-secondary')} onClick={() => setFeedbackUseful(true)}>有用</button>
            <button className={cn('rounded-md border px-3 py-2 text-sm', feedbackUseful === false ? 'border-severity-critical bg-severity-critical/10 text-severity-critical' : 'border-border text-text-secondary')} onClick={() => setFeedbackUseful(false)}>没帮助</button>
          </div>
          {feedbackUseful !== null && (
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              {priorityFixes.length > 0 && (
                <fieldset className="text-xs text-text-secondary sm:col-span-3">
                  <legend className="mb-2">实际准备采纳哪些建议？</legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {priorityFixes.map((fix, i) => {
                      const title = fix.issue ?? `建议 ${i + 1}`
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
              <label className="text-xs text-text-secondary">预计节省工时
                <input type="number" min={0} step="0.5" value={hoursSaved} onChange={(e) => setHoursSaved(Number(e.target.value))} className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 text-text-primary" />
              </label>
              <label className="text-xs text-text-secondary">愿意为本次支付（USD）
                <input type="number" min={0} step="1" value={willingnessToPay} onChange={(e) => setWillingnessToPay(Number(e.target.value))} className="mt-1 w-full rounded-md border border-border bg-bg-secondary px-3 py-2 text-text-primary" />
              </label>
              <label className="flex items-center gap-2 text-xs text-text-secondary sm:col-span-2">
                <input type="checkbox" checked={decisionChanged} onChange={(e) => setDecisionChanged(e.target.checked)} className="accent-brand-primary" />
                报告改变了我的产品或发布决策
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
                  setFeedbackError(error instanceof Error ? error.message : '反馈提交失败')
                }
              }}>提交反馈</button>
            </div>
          )}
          {feedbackError && <p className="mt-3 text-xs text-severity-critical">{feedbackError}</p>}
        </section>
      )}
      {feedbackSent && <p className="mb-6 text-sm text-brand-primary">已记录。后续可在"判断复利"查看价值指标。</p>}
    </div>
  )
}

// ---------- 匿名体验版 ----------

function GatedReportTeaser({ review, gated }: { review: Review | null; gated: RealReport }) {
  const summary = gated.executive_summary
  const fix = gated.priority_fixes?.[0]
  const fixesHidden = gated.gated_counts?.priority_fixes_hidden ?? 0
  const notesHidden = gated.gated_counts?.persona_notes_hidden ?? 0

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

      <div className="flex items-center gap-3 mb-6">
        <Link to={review ? `/review/${review.id}` : '/'} className="p-2 rounded-lg hover:bg-bg-card transition-colors">
          <ArrowLeft className="w-5 h-5 text-text-secondary" strokeWidth={1.25} />
        </Link>
        <div>
          <h1 className="text-xl font-semibold text-text-primary">{review?.target_title ?? '评审报告'}</h1>
          <p className="text-sm text-text-secondary">体验版报告</p>
        </div>
      </div>

      {summary && (
        <div className="rounded-xl border border-border bg-bg-card p-5 mb-4">
          <h2 className="text-sm font-medium text-text-muted mb-3">执行摘要</h2>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-text-muted text-xs">发布风险</dt>
              <dd className="mt-1 font-medium text-text-primary">
                {RISK_CONFIG[summary.release_risk ?? '']?.label ?? summary.release_risk ?? '—'}
              </dd>
            </div>
            <div>
              <dt className="text-text-muted text-xs">证据充分度</dt>
              <dd className="mt-1 font-medium text-text-primary">
                {EVIDENCE_QUALITY_LABELS[summary.evidence_quality ?? ''] ?? summary.evidence_quality ?? '—'}
              </dd>
            </div>
            {summary.primary_recommendation && (
              <div className="col-span-2 sm:col-span-3">
                <dt className="text-text-muted text-xs">主要建议</dt>
                <dd className="mt-1 font-medium text-text-primary">{summary.primary_recommendation}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {fix && (
        <div className="rounded-xl border border-border bg-bg-card p-5 mb-4">
          <h2 className="text-sm font-medium text-text-muted mb-3">优先修复项（预览）</h2>
          <p className="font-medium text-text-primary">{fix.issue}</p>
          {fix.why_it_matters && <p className="mt-1 text-sm text-text-secondary">{fix.why_it_matters}</p>}
        </div>
      )}

      <div className="rounded-xl border border-brand-primary/30 bg-brand-primary/5 p-6 text-center">
        <Lock className="w-6 h-6 text-brand-primary mx-auto mb-3" strokeWidth={1.5} />
        <p className="text-text-primary font-medium">
          还有 {fixesHidden} 条优先修复项、{notesHidden} 条角色视角未展示
        </p>
        {/* 这句话必须和代码对得上。匿名评审落库时 user_id="anonymous"，登录后
            身份变了就再也打不开——所以"报告会保存在你的历史记录里"只有在认领
            链路真的存在时才成立（apiClient 的待认领清单 + POST
            /api/auth/me/claim-reviews）。认领靠的是这台浏览器本地记下的 id，
            所以"在这台设备上"不是废话，是这句承诺真实的边界。 */}
        <p className="mt-1 text-sm text-text-secondary">
          在这台设备上登录或注册后，这份报告会自动归到你的账号名下，完整内容和历史记录都能在「评审历史」里打开。
        </p>
        <Link
          to="/login"
          className="mt-4 inline-block rounded-lg bg-brand-primary px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors"
        >
          登录 / 注册看完整报告
        </Link>
      </div>

      <div className="mt-6">
        <LimitationsSection caveats={gated.meta?.caveats} />
      </div>
    </div>
  )
}

// ---------- 导出兜底（无服务端 markdown 时按真实字段现拼） ----------

function generateMarkdown(report: RealReport): string {
  const lines: string[] = []
  const summary = report.executive_summary
  lines.push('# 评审报告')
  lines.push('')
  // 服务端的 markdown 走 src/templates/report-template.md，顶部自带 Synthetic Banner。
  // 这条兜底路径此前直接从"# 评审报告"开始，导出的文件里一句合成声明都没有。
  lines.push('> **合成评审面板：以下全部意见由 AI 人格生成，不是真实玩家/用户的反馈。**')
  lines.push('> 本报告不得作为「玩家调研结果」「用户调查数据」「真实玩家意见分布」对外展示或引用。')
  lines.push('')
  if (report.degradation?.degraded && report.degradation.notice) {
    lines.push(`> **⚠️ ${report.degradation.notice}**`)
    lines.push('')
  }
  // 导出件同样是"一份报告"：网页上置顶的两条坏消息（谁被校验拦下、
  // 有没有因为预算跳过环节）不能只存在于网页里
  const gatedOut = (report.validation?.gated_out ?? []).filter((g) => g.persona_id)
  if (gatedOut.length) {
    lines.push(`> **⚠️ 有 ${gatedOut.length} 位人格的输出没通过质量校验，未计入以下结论：**`)
    for (const g of gatedOut) {
      const reason = g.failure_reason
        ? GATE_REASON_LABELS[g.failure_reason] ?? `未知失败类型（${g.failure_reason}）`
        : '引擎没有回传失败类型'
      lines.push(`> - ${g.persona_id}：${reason}`)
    }
    lines.push('')
  }
  if (report.budget?.exceeded) {
    const notice = report.budget.notice?.trim() || '本次评审达到了单次成本上限。'
    lines.push(`> **⚠️ ${notice}**`)
    if ((report.budget.skipped_stages ?? []).includes('cross_examination')) {
      lines.push('> 交叉质询未执行——本报告没有这一节，不代表人格之间没有分歧。')
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
    lines.push(`## 发布风险：${RISK_CONFIG[summary.release_risk ?? '']?.label ?? summary.release_risk ?? '未知'}`)
    lines.push('')
    lines.push(`- 主流立场：${summary.primary_recommendation ?? '—'}`)
    lines.push(`- 证据充分度：${EVIDENCE_QUALITY_LABELS[summary.evidence_quality ?? ''] ?? summary.evidence_quality ?? '—'}`)
    lines.push('')
  }
  const fixes = report.priority_fixes ?? []
  if (fixes.length) {
    lines.push('## 优先修复项')
    lines.push('')
    for (const fix of fixes) {
      lines.push(`### [${(fix.severity ?? 'medium').toUpperCase()}] ${fix.issue ?? ''}`)
      lines.push('')
      if (fix.why_it_matters) lines.push(fix.why_it_matters)
      if (fix.suggested_fix) lines.push(`**建议**：${fix.suggested_fix}`)
      lines.push('')
    }
  }
  // 交叉质询：这条兜底路径里也必须写清楚是三档里的哪一种。导出件同样是"一份报告"，
  // 少了这句话，读者只会按最强的那一档（多智能体反驳）理解。
  const crossExam = toCrossExamView(report.cross_examination)
  if (crossExam) {
    lines.push('## 交叉质询')
    lines.push('')
    if (crossExam.is_legacy_array) {
      lines.push('这份报告由旧版本生成，交叉质询记录格式过旧，无法解析出反驳与改票明细。')
    } else {
      const label = crossExam.mode ? CROSS_EXAM_MODE_LABELS[crossExam.mode] : `未知模式（${crossExam.mode_raw}）`
      lines.push(`- 执行方式：${label}`)
      const desc = crossExam.mode ? CROSS_EXAM_MODE_DESCRIPTIONS[crossExam.mode] : '无法判断是否真的发生过反驳。'
      lines.push(`- ${desc}`)
      if (crossExam.limitation) lines.push(`- 引擎说明：${crossExam.limitation}`)
      lines.push(
        crossExam.is_live_debate
          ? `- 改票记录：${crossExam.vote_changes.length} 条${crossExam.vote_changes.length === 0 ? '（本轮双方立场未变，属正常结果）' : ''}`
          : '- 改票记录：不适用（未进行反驳轮）'
      )
      if (crossExam.failures.length) {
        lines.push(`- 过程中有 ${crossExam.failures.length} 条失败：${crossExam.failures.map((f) => f.error).join('；')}`)
      }
    }
    lines.push('')
  } else {
    // 整节缺席也要写出来：导出件里少一节，读者只会当"这次没什么争议"
    lines.push('## 交叉质询')
    lines.push('')
    lines.push(
      report.budget?.exceeded && (report.budget.skipped_stages ?? []).includes('cross_examination')
        ? '本次没有执行交叉质询：成本已达单次上限，为免继续加钱而跳过。这不代表人格之间没有分歧。'
        : '这份报告里没有交叉质询记录，报告也没有写明原因（可能是这一档评审模式不包含反驳环节，也可能是没有出现值得反驳的对立观点）。请不要读成"大家意见一致"。'
    )
    lines.push('')
  }
  const gaps = report.information_gaps ?? []
  if (gaps.length) {
    lines.push('## 信息缺口')
    lines.push('')
    gaps.forEach((g, i) => lines.push(`${i + 1}. ${g}`))
    lines.push('')
  }
  // ETHICS.md 要求每份报告都带 Limitations & Caveats——导出件同样算"一份报告"
  lines.push('## 局限与注意事项（Limitations & Caveats）')
  lines.push('')
  for (const item of [...(report.meta?.caveats ?? []), ...LIMITATIONS]) {
    lines.push(`- ${item}`)
  }
  lines.push('')
  return lines.join('\n')
}
