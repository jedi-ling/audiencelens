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
 */

import { useParams, Link } from 'react-router'
import { useState, useEffect, useRef } from 'react'
import { fetchReview, fetchReport, fetchReviewResult, fetchEvaluation, fetchEthicsReport, runEvaluation } from '@/lib/api'
import { cn } from '@/lib/utils'
import { api } from '@/lib/apiClient'
import type { Review, ReviewMode, EvaluationScorecard, EthicsReportView, Severity } from '@/lib/mock-data'
import {
  EVALUATION_DIMENSIONS,
  ETHICS_SEVERITY_BADGE_CLASSES,
  ETHICS_SEVERITY_LABELS,
  stereotypeRiskBadgeClass,
  stereotypeRiskLabel,
  toEthicsReportView,
} from '@/lib/mock-data'
import SeverityBadge from '@/components/SeverityBadge'
import CalibrationGauge from '@/components/CalibrationGauge'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import { ArrowLeft, ChevronDown, ChevronUp, AlertTriangle, Loader2, File, FileText, Globe, Shield, FlaskConical, AlertOctagon, Lock, Users, HelpCircle, Scale, Zap, ListChecks, Microscope, CheckCircle2, XCircle } from 'lucide-react'

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

interface RealReport {
  meta?: { task_type?: string; target?: string; generated_at?: string; is_synthetic?: boolean } | null
  executive_summary?: { primary_recommendation?: string; release_risk?: string; evidence_quality?: string } | null
  consensus?: { agreed_points?: string[]; questioned_points?: string[] } | null
  major_disagreements?: RealDisagreement[]
  priority_fixes?: RealPriorityFix[]
  persona_notes?: RealPersonaNote[]
  information_gaps?: string[]
  next_human_test?: { suggested_tasks?: string[]; recruit_types?: string[]; next_materials?: string[] } | null
  cross_examination?: unknown
  compliance?: { status?: string; ethics_score?: number; recommended_steps?: string[] } | null
  simulation_notice?: string | null
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
  low: { label: '低风险', color: 'text-neon-green', bg: 'bg-neon-green/10', border: 'border-neon-green/30' },
  medium: { label: '中风险', color: 'text-severity-medium', bg: 'bg-severity-medium/10', border: 'border-severity-medium/30' },
  high: { label: '高风险', color: 'text-warm-orange', bg: 'bg-warm-orange/10', border: 'border-warm-orange/30' },
  critical: { label: '极高风险', color: 'text-severity-critical', bg: 'bg-severity-critical/10', border: 'border-severity-critical/30' },
}

const EVIDENCE_QUALITY_LABELS: Record<string, string> = {
  strong: '充分',
  medium: '中等',
  weak: '偏弱',
  insufficient: '不足',
}

// 立场是各任务类型自己的枚举（"加愿望单"/"值得推进"/"观望"…），无法穷举——按出现顺序配色
// 首色用绸缎金 #F9D67D 而非品牌主色 #B77E3B：主色明度太低，紧邻 #ffbb33 会糊成一团
const STANCE_PALETTE = ['#F9D67D', '#ffbb33', '#ff6b35', '#ff3355', '#4ECDC4', '#a78bfa']

const MODE_BADGE: Record<ReviewMode, { label: string; color: string; bg: string; Icon: typeof Zap }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', Icon: Zap },
  standard: { label: '标准', color: 'text-neon-green', bg: 'bg-neon-green/10', Icon: ListChecks },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', Icon: Microscope },
}

const VALID_SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low']

function noteStance(note: RealPersonaNote): string {
  return note.stance ?? note.primary_stance ?? '未表态'
}

export default function ReportPage() {
  const { id } = useParams()
  const [review, setReview] = useState<Review | null>(null)
  const [report, setReport] = useState<RealReport | null>(null)
  const [calibration, setCalibration] = useState<RealCalibration | null>(null)
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null)
  const [reportHtml, setReportHtml] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedIssues, setExpandedIssues] = useState<Set<number>>(new Set())
  const [showHtmlReport, setShowHtmlReport] = useState(false)
  const [evaluationScorecard, setEvaluationScorecard] = useState<EvaluationScorecard | null>(null)
  // 存收敛后的视图：违规项与风险档位在进 state 前就已经过类型守卫
  const [ethicsReports, setEthicsReports] = useState<EthicsReportView[]>([])
  const [expandedDimensions, setExpandedDimensions] = useState<Set<string>>(new Set())
  const [evaluating, setEvaluating] = useState(false)
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [feedbackUseful, setFeedbackUseful] = useState<boolean | null>(null)
  const [decisionChanged, setDecisionChanged] = useState(false)
  const [adoptedFixes, setAdoptedFixes] = useState<string[]>([])
  const [hoursSaved, setHoursSaved] = useState(0)
  const [willingnessToPay, setWillingnessToPay] = useState(0)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const iframeRef = useRef<HTMLIFrameElement>(null)

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
    const loadData = async () => {
      try {
        const [reviewData, reportData] = await Promise.all([fetchReview(id), fetchReport(id)])
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
      } catch {
        // 报告尚未生成时走下面的空态分支
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [id])

  useEffect(() => {
    if (!id) return
    fetchReviewResult(id)
      .then((result) => {
        if (result.report_html) setReportHtml(result.report_html)
        if (result.report_md && !reportMarkdown) setReportMarkdown(result.report_md)
      })
      .catch(() => {})
  }, [id, reportMarkdown])

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

  if (report?.is_gated) {
    return <GatedReportTeaser review={review} gated={report} />
  }

  if (!review || !report) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <p className="text-text-secondary">报告尚未生成</p>
        <Link to={`/review/${id}`} className="text-cyan hover:text-cyan-dim mt-4 inline-block">查看进度</Link>
      </div>
    )
  }

  const summary = report.executive_summary
  const risk = RISK_CONFIG[summary?.release_risk ?? ''] ?? RISK_CONFIG.medium
  const reviewMode = (review.mode ?? 'standard') as ReviewMode
  const modeBadge = MODE_BADGE[reviewMode] ?? MODE_BADGE.standard
  const priorityFixes = report.priority_fixes ?? []
  const personaNotes = report.persona_notes ?? []
  const disagreements = report.major_disagreements ?? []
  const informationGaps = report.information_gaps ?? []

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
      content = reportHtml ?? '<!DOCTYPE html><html><body><p>HTML报告尚未生成</p></body></html>'
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
            onClick={() => handleExport('json')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card border border-border text-sm text-text-secondary hover:border-neon-green/30 hover:text-neon-green transition-all"
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
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card border border-border text-sm text-text-secondary hover:border-warm-orange/30 hover:text-warm-orange transition-all"
          >
            <Globe className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">HTML</span>
          </button>
        </div>
      </div>

      {report.simulation_notice && (
        <div className="mb-6 rounded-xl border-2 border-severity-critical/40 bg-severity-critical/10 p-4 text-sm text-text-primary">
          {report.simulation_notice}
        </div>
      )}

      {reportHtml && (
        <div className="mb-6">
          <button
            onClick={() => setShowHtmlReport(!showHtmlReport)}
            className={cn(
              'w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-all',
              showHtmlReport
                ? 'bg-neon-green/5 border-neon-green/30'
                : 'bg-bg-card border-border hover:border-neon-green/30'
            )}
          >
            <span className="flex items-center gap-2 text-sm font-medium text-text-secondary">
              <Globe className="w-4 h-4 text-neon-green" strokeWidth={1.25} />
              HTML 可视化报告
            </span>
            {showHtmlReport
              ? <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
              : <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
            }
          </button>
          {showHtmlReport && (
            <div className="mt-3 rounded-xl border border-border overflow-hidden bg-white">
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
      <div className={cn('rounded-xl border-2 p-4 md:p-6 mb-6', risk.bg, risk.border)}>
        <div className="flex items-center gap-3 mb-3">
          <AlertTriangle className={cn('w-5 h-5 md:w-6 md:h-6', risk.color)} strokeWidth={1.25} />
          <h2 className={cn('text-base md:text-lg font-bold font-display', risk.color)}>
            发布风险评估：{risk.label}
          </h2>
        </div>
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
            <dt className="text-xs text-text-muted">共识点 / 存疑点</dt>
            <dd className="mt-1 font-medium text-text-primary">
              {(report.consensus?.agreed_points?.length ?? 0)} / {(report.consensus?.questioned_points?.length ?? 0)}
            </dd>
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
                      contentStyle={{ backgroundColor: '#16161f', border: '1px solid #2a2a3a', borderRadius: '8px', fontSize: '12px' }}
                      itemStyle={{ color: '#e8e8f0' }}
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
              <div className="flex justify-around">
                <CalibrationGauge label="角色一致性" value={calibration.role_consistency?.average ?? 0} />
                <CalibrationGauge label="视角覆盖度" value={calibration.coverage?.average_distance ?? 0} />
                {calibration.hallucination != null && (
                  <CalibrationGauge label="无幻觉率" value={1 - (calibration.hallucination.average ?? 0)} />
                )}
              </div>
              {calibration.overall_pass != null && (
                <p className={cn(
                  'mt-3 text-center text-xs font-medium',
                  calibration.overall_pass ? 'text-neon-green' : 'text-warm-orange'
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
                            <span className="text-neon-green mt-0.5">•</span>
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
                <dt className="text-xs text-text-muted mb-1">建议招募的人群</dt>
                <dd className="text-text-secondary">
                  {(report.next_human_test.recruit_types ?? []).join('、') || '—'}
                </dd>
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
                ? 'bg-neon-green/10 text-neon-green'
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
              <h4 className="text-sm font-medium text-text-muted mb-4">总体评分</h4>
              <div className="flex items-center gap-4">
                <div className={cn(
                  'w-20 h-20 rounded-full flex items-center justify-center border-4',
                  evaluationScorecard.overall_score > 70
                    ? 'border-neon-green bg-neon-green/10'
                    : evaluationScorecard.overall_score >= 50
                      ? 'border-severity-medium bg-severity-medium/10'
                      : 'border-severity-critical bg-severity-critical/10'
                )}>
                  <span className={cn(
                    'text-2xl font-bold font-mono',
                    evaluationScorecard.overall_score > 70
                      ? 'text-neon-green'
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
                      ? 'bg-neon-green/10 text-neon-green'
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
              <h4 className="text-sm font-medium text-text-muted mb-4">维度评分</h4>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={evaluationScorecard.results.map((r) => {
                  const dim = EVALUATION_DIMENSIONS.find((d) => d.id === r.dimension)
                  return {
                    name: dim?.name ?? r.dimension,
                    score: r.score,
                    fill: r.passed ? '#B77E3B' : '#ff3355',
                  }
                })}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#8888a0' }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#8888a0' }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#16161f', border: '1px solid #2a2a3a', borderRadius: '8px', fontSize: '12px' }}
                    itemStyle={{ color: '#e8e8f0' }}
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
                      'w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold font-mono',
                      result.passed ? 'bg-neon-green/10 text-neon-green' : 'bg-severity-critical/10 text-severity-critical'
                    )}>
                      {result.score}
                    </div>
                    <div className="flex-1 min-w-0">
                      <span className="text-sm font-medium text-text-primary">{dim?.name ?? result.dimension}</span>
                      <span className={cn(
                        'ml-2 text-xs px-1.5 py-0.5 rounded',
                        result.passed ? 'bg-neon-green/10 text-neon-green' : 'bg-severity-critical/10 text-severity-critical'
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
                      <p className="text-xs text-text-muted mb-1">{dim?.description}</p>
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
                    er.passed ? 'bg-neon-green/10 text-neon-green' : 'bg-severity-critical/10 text-severity-critical'
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
                        er.score > 70 ? 'text-neon-green' : er.score >= 50 ? 'text-severity-medium' : 'text-severity-critical'
                      )}>
                        {er.score}
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-bg-secondary overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          er.score > 70 ? 'bg-neon-green' : er.score >= 50 ? 'bg-severity-medium' : 'bg-severity-critical'
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
                              <code className="text-[10px] font-mono text-gold-cream break-all">{v.rule}</code>
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

      <div className="flex flex-wrap gap-3 mb-6">
        <button
          onClick={async () => {
            if (!id) return
            setEvaluating(true)
            try {
              const result = await runEvaluation(id)
              setEvaluationScorecard(result)
            } catch {
              // 评估请求失败：保留页面现有内容，仅结束加载态
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
      </div>

      {/* ---------- 价值回填 ---------- */}
      {id && !feedbackSent && (
        <section className="mb-6 rounded-xl border border-neon-green/30 bg-bg-card p-5">
          <h2 className="font-display text-sm font-semibold text-text-primary">这份报告真的有用吗？</h2>
          <p className="mt-1 text-xs text-text-muted">反馈将用于衡量建议采纳与决策影响，不用调用次数冒充价值。</p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button className={cn('rounded-md border px-3 py-2 text-sm', feedbackUseful === true ? 'border-neon-green bg-neon-green/10 text-neon-green' : 'border-border text-text-secondary')} onClick={() => setFeedbackUseful(true)}>有用</button>
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
                          <input type="checkbox" checked={adoptedFixes.includes(title)} onChange={(e) => setAdoptedFixes((current) => e.target.checked ? [...current, title] : current.filter((t) => t !== title))} className="mt-0.5 accent-neon-green" />
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
                <input type="checkbox" checked={decisionChanged} onChange={(e) => setDecisionChanged(e.target.checked)} className="accent-neon-green" />
                报告改变了我的产品或发布决策
              </label>
              <button className="rounded-md bg-neon-green px-4 py-2 text-sm font-semibold text-bg-primary" onClick={async () => {
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
      {feedbackSent && <p className="mb-6 text-sm text-neon-green">已记录。后续可在"判断复利"查看价值指标。</p>}
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

      <div className="rounded-xl border border-neon-green/30 bg-neon-green/5 p-6 text-center">
        <Lock className="w-6 h-6 text-neon-green mx-auto mb-3" strokeWidth={1.5} />
        <p className="text-text-primary font-medium">
          还有 {fixesHidden} 条优先修复项、{notesHidden} 条角色视角未展示
        </p>
        <p className="mt-1 text-sm text-text-secondary">登录后可查看完整报告，且报告会保存在你的历史记录里</p>
        <Link
          to="/login"
          className="mt-4 inline-block rounded-lg bg-neon-green px-5 py-2.5 text-sm font-semibold text-bg-primary hover:bg-neon-green-dim transition-colors"
        >
          登录查看完整报告
        </Link>
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
  const gaps = report.information_gaps ?? []
  if (gaps.length) {
    lines.push('## 信息缺口')
    lines.push('')
    gaps.forEach((g, i) => lines.push(`${i + 1}. ${g}`))
    lines.push('')
  }
  return lines.join('\n')
}
