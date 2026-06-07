import { useParams, Link } from 'react-router'
import { useState, useEffect, useRef } from 'react'
import { fetchReview, fetchReport, fetchReviewResult, fetchEvaluation, fetchEthicsReport, runEvaluation } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { Report, RiskLevel, PrimaryStance, Review, ReviewMode, EvaluationScorecard, EthicsReport } from '@/lib/mock-data'
import { EVALUATION_DIMENSIONS } from '@/lib/mock-data'
import SeverityBadge from '@/components/SeverityBadge'
import CalibrationGauge from '@/components/CalibrationGauge'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid } from 'recharts'
import { ArrowLeft, Download, ChevronDown, ChevronUp, AlertTriangle, Quote, Loader2, File, FileText, Globe, Shield, FlaskConical, AlertOctagon } from 'lucide-react'

const riskConfig: Record<RiskLevel, { label: string; color: string; bg: string; border: string }> = {
  green: { label: '低风险', color: 'text-neon-green', bg: 'bg-neon-green/10', border: 'border-neon-green/30' },
  yellow: { label: '中风险', color: 'text-severity-medium', bg: 'bg-severity-medium/10', border: 'border-severity-medium/30' },
  orange: { label: '高风险', color: 'text-warm-orange', bg: 'bg-warm-orange/10', border: 'border-warm-orange/30' },
  red: { label: '极高风险', color: 'text-severity-critical', bg: 'bg-severity-critical/10', border: 'border-severity-critical/30' },
}

const stanceColors: Record<PrimaryStance, string> = {
  advocate: '#00ff88',
  neutral: '#ffbb33',
  skeptic: '#ff6b35',
  blocker: '#ff3355',
}

const stanceLabels: Record<PrimaryStance, string> = {
  advocate: '支持',
  neutral: '中立',
  skeptic: '质疑',
  blocker: '反对',
}

const modeBadgeConfig: Record<ReviewMode, { label: string; color: string; bg: string; icon: string }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', icon: '⚡' },
  standard: { label: '标准', color: 'text-neon-green', bg: 'bg-neon-green/10', icon: '✅' },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', icon: '🔬' },
}

export default function ReportPage() {
  const { id } = useParams()
  const [review, setReview] = useState<Review | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null)
  const [reportHtml, setReportHtml] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [expandedIssues, setExpandedIssues] = useState<Set<string>>(new Set())
  const [showHtmlReport, setShowHtmlReport] = useState(false)
  const [evaluationScorecard, setEvaluationScorecard] = useState<EvaluationScorecard | null>(null)
  const [ethicsReports, setEthicsReports] = useState<EthicsReport[]>([])
  const [expandedDimensions, setExpandedDimensions] = useState<Set<string>>(new Set())
  const [evaluating, setEvaluating] = useState(false)
  const [redTeaming, setRedTeaming] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  const toggleIssue = (issueId: string) => {
    setExpandedIssues((prev) => {
      const next = new Set(prev)
      if (next.has(issueId)) next.delete(issueId)
      else next.add(issueId)
      return next
    })
  }

  useEffect(() => {
    if (!id) return
    const loadData = async () => {
      try {
        const [reviewData, reportData] = await Promise.all([
          fetchReview(id),
          fetchReport(id),
        ])
        setReview(reviewData)
        if (reportData.report_json) {
          const reportObj = reportData.report_json as Report
          if (reportData.calibration) {
            reportObj.calibration = reportData.calibration as Report['calibration']
          }
          setReport(reportObj)
        }
        if (reportData.report_markdown) {
          setReportMarkdown(reportData.report_markdown)
        }
      } catch {
        // ignore
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
        if (result.report_html) {
          setReportHtml(result.report_html)
        }
        if (result.report_md && !reportMarkdown) {
          setReportMarkdown(result.report_md)
        }
      })
      .catch(() => {})
  }, [id, reportMarkdown])

  useEffect(() => {
    if (!id) return
    fetchEvaluation(id)
      .then((data) => setEvaluationScorecard(data))
      .catch(() => {})
    fetchEthicsReport(id)
      .then((data) => setEthicsReports(data))
      .catch(() => {})
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

  if (!review || !report) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <p className="text-text-secondary">报告尚未生成</p>
        <Link to={`/review/${id}`} className="text-cyan hover:text-cyan-dim mt-4 inline-block">查看进度</Link>
      </div>
    )
  }

  const risk = riskConfig[report.riskLevel]
  const reviewMode = (review.mode ?? 'standard') as ReviewMode
  const modeBadge = modeBadgeConfig[reviewMode] ?? modeBadgeConfig.standard

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
          <h1 className="text-xl font-semibold text-text-primary truncate">{review.target_title}</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-text-secondary">评审报告</p>
            <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', modeBadge.bg, modeBadge.color)}>
              <span>{modeBadge.icon}</span>
              {modeBadge.label}模式
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => handleExport('json')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card border border-border text-sm text-text-secondary hover:border-neon-green/30 hover:text-neon-green transition-all"
          >
            <Download className="w-3.5 h-3.5" strokeWidth={1.25} />
            <File className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">JSON</span>
          </button>
          <button
            onClick={() => handleExport('markdown')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card border border-border text-sm text-text-secondary hover:border-cyan/30 hover:text-cyan transition-all"
          >
            <Download className="w-3.5 h-3.5" strokeWidth={1.25} />
            <FileText className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">MD</span>
          </button>
          <button
            onClick={() => handleExport('html')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-card border border-border text-sm text-text-secondary hover:border-warm-orange/30 hover:text-warm-orange transition-all"
          >
            <Download className="w-3.5 h-3.5" strokeWidth={1.25} />
            <Globe className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="hidden sm:inline">HTML</span>
          </button>
        </div>
      </div>

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

      <div className={cn('rounded-xl border-2 p-4 md:p-6 mb-6', risk.bg, risk.border)}>
        <div className="flex items-center gap-3 mb-3">
          <AlertTriangle className={cn('w-5 h-5 md:w-6 md:h-6', risk.color)} strokeWidth={1.25} />
          <h2 className={cn('text-base md:text-lg font-bold font-display', risk.color)}>发布风险评估：{risk.label}</h2>
        </div>
        <p className="text-text-secondary leading-relaxed text-sm md:text-base">{report.riskSummary}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <h3 className="text-sm font-medium text-text-muted mb-4">立场分布</h3>
          <div className="min-h-[180px] md:min-h-[220px]">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie
                data={report.stanceDistribution.map((d) => ({
                  name: stanceLabels[d.stance],
                  value: d.count,
                  stance: d.stance,
                }))}
                cx="50%"
                cy="50%"
                innerRadius={40}
                outerRadius={70}
                paddingAngle={3}
                dataKey="value"
              >
                {report.stanceDistribution.map((d, i) => (
                  <Cell key={i} fill={stanceColors[d.stance]} fillOpacity={0.8} stroke={stanceColors[d.stance]} strokeWidth={1} />
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
            {report.stanceDistribution.map((d) => (
              <div key={d.stance} className="flex items-center gap-1.5 text-xs">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: stanceColors[d.stance] }} />
                <span className="text-text-secondary">{stanceLabels[d.stance]}</span>
                <span className="font-mono text-text-muted">{d.count}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <h3 className="text-sm font-medium text-text-muted mb-4">校准指标</h3>
          <div className="flex justify-around">
            <CalibrationGauge label="一致性" value={report.calibration.consistency} />
            <CalibrationGauge label="覆盖率" value={report.calibration.coverage} />
            <CalibrationGauge label="幻觉率" value={1 - report.calibration.hallucination} />
          </div>
        </div>
      </div>

      <div className="mb-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">优先修复项</h3>
        <div className="flex flex-col gap-3">
          {report.priorityIssues.map((issue) => {
            const expanded = expandedIssues.has(issue.id)
            return (
              <div key={issue.id} className="rounded-xl border border-border bg-bg-card overflow-hidden">
                <button
                  onClick={() => toggleIssue(issue.id)}
                  className="w-full flex items-center gap-3 px-4 md:px-5 py-4 text-left hover:bg-bg-card-hover transition-colors"
                >
                  <SeverityBadge severity={issue.severity} />
                  <span className="flex-1 text-sm font-medium text-text-primary">{issue.title}</span>
                  {expanded ? (
                    <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                  )}
                </button>
                {expanded && (
                  <div className="px-4 md:px-5 pb-4 border-t border-border pt-3">
                    <p className="text-sm text-text-secondary mb-3">{issue.description}</p>
                    {issue.evidence.length > 0 && (
                      <div className="mb-3">
                        <h4 className="text-xs font-medium text-text-muted mb-1.5">证据</h4>
                        <ul className="space-y-1">
                          {issue.evidence.map((e, i) => (
                            <li key={i} className="text-xs text-text-secondary flex items-start gap-1.5">
                              <span className="text-cyan mt-0.5">•</span>
                              {e}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {issue.affectedPersonas.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-text-muted mb-1.5">相关角色</h4>
                        <div className="flex flex-wrap gap-1.5">
                          {issue.affectedPersonas.map((p) => (
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

      <div className="mb-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">角色视角</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {report.personaPerspectives.map((pp) => (
            <div key={pp.personaId} className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
              <div className="flex items-center gap-2 mb-3">
                <span className="font-medium text-text-primary">{pp.personaName}</span>
                <span className="text-xs text-text-muted">{pp.archetype}</span>
                <span
                  className="ml-auto text-xs font-medium px-2 py-0.5 rounded"
                  style={{
                    backgroundColor: stanceColors[pp.stance as PrimaryStance]
                      ? `${stanceColors[pp.stance as PrimaryStance]}1a`
                      : undefined,
                    color: stanceColors[pp.stance as PrimaryStance] ?? undefined,
                  }}
                >
                  {stanceLabels[pp.stance as PrimaryStance] ?? pp.stance}
                </span>
              </div>

              <div className="flex items-start gap-2 mb-3 bg-bg-secondary/50 rounded-lg p-3">
                <Quote className="w-4 h-4 text-text-muted shrink-0 mt-0.5" strokeWidth={1.25} />
                <p className="text-sm text-text-secondary italic leading-relaxed">{pp.quote}</p>
              </div>

              <div className="flex items-center gap-2 text-xs">
                <span className="text-text-muted">置信度</span>
                <span className="font-mono text-cyan">{(pp.confidence * 100).toFixed(0)}%</span>
              </div>

              {pp.keyEvidence.length > 0 && (
                <div className="mt-2">
                  <h4 className="text-xs text-text-muted mb-1">关键证据</h4>
                  <ul className="space-y-0.5">
                    {pp.keyEvidence.map((e, i) => (
                      <li key={i} className="text-xs text-text-secondary flex items-start gap-1.5">
                        <span className="text-neon-green mt-0.5">•</span>
                        {e}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {report.informationGaps.length > 0 && (
        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5 mb-6">
          <h3 className="text-lg font-semibold text-text-primary mb-4">信息缺口</h3>
          <ul className="space-y-2">
            {report.informationGaps.map((gap, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                <span className="text-warm-orange font-display shrink-0">{i + 1}.</span>
                {gap}
              </li>
            ))}
          </ul>
        </div>
      )}

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
                    {evaluationScorecard.passed ? '✅ 通过' : '❌ 未通过'}
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
                    fill: r.passed ? '#00ff88' : '#ff3355',
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
                    'text-xs px-2 py-0.5 rounded font-medium',
                    er.passed ? 'bg-neon-green/10 text-neon-green' : 'bg-severity-critical/10 text-severity-critical'
                  )}>
                    {er.passed ? '✅ 通过' : '❌ 未通过'}
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
                  <div className="flex-1">
                    <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                      <span>刻板印象风险</span>
                      <span className={cn(
                        'font-mono font-bold',
                        er.stereotype_risk < 0.3 ? 'text-neon-green' : er.stereotype_risk < 0.6 ? 'text-severity-medium' : 'text-severity-critical'
                      )}>
                        {(er.stereotype_risk * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="w-full h-1.5 rounded-full bg-bg-secondary overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all',
                          er.stereotype_risk < 0.3 ? 'bg-neon-green' : er.stereotype_risk < 0.6 ? 'bg-severity-medium' : 'bg-severity-critical'
                        )}
                        style={{ width: `${er.stereotype_risk * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
                {er.violations.length > 0 && (
                  <div>
                    <h4 className="text-xs font-medium text-text-muted mb-1.5">违规项</h4>
                    <div className="flex flex-wrap gap-1">
                      {er.violations.map((v, i) => (
                        <span key={i} className="px-2 py-0.5 rounded text-xs bg-severity-critical/10 text-severity-critical">
                          {v}
                        </span>
                      ))}
                    </div>
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
            } catch {} finally {
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
        <button
          onClick={async () => {
            if (!id) return
            setRedTeaming(true)
            try {
              await runEvaluation(id)
            } catch {} finally {
              setRedTeaming(false)
            }
          }}
          disabled={redTeaming}
          className={cn(
            'flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all',
            redTeaming
              ? 'bg-bg-card text-text-muted cursor-not-allowed'
              : 'bg-red-400/10 text-red-400 border border-red-400/30 hover:bg-red-400/20'
          )}
        >
          {redTeaming ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} /> : <Shield className="w-4 h-4" strokeWidth={1.25} />}
          运行红队
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
    </div>
  )
}

function generateMarkdown(report: Report): string {
  if (!report) return ''
  const lines: string[] = []
  lines.push('# 评审报告')
  lines.push('')
  lines.push(`## 发布风险评估：${riskConfig[report.riskLevel as RiskLevel].label}`)
  lines.push('')
  lines.push(report.riskSummary)
  lines.push('')
  lines.push('## 立场分布')
  lines.push('')
  report.stanceDistribution.forEach((d: { stance: PrimaryStance; count: number }) => {
    lines.push(`- ${stanceLabels[d.stance]}: ${d.count}`)
  })
  lines.push('')
  lines.push('## 优先修复项')
  lines.push('')
  report.priorityIssues.forEach((issue) => {
    lines.push(`### [${issue.severity.toUpperCase()}] ${issue.title}`)
    lines.push('')
    lines.push(issue.description)
    lines.push('')
    if (issue.evidence.length) {
      lines.push('**证据：**')
      issue.evidence.forEach((e: string) => lines.push(`- ${e}`))
      lines.push('')
    }
  })
  lines.push('## 信息缺口')
  lines.push('')
  report.informationGaps.forEach((g: string, i: number) => lines.push(`${i + 1}. ${g}`))
  lines.push('')
  return lines.join('\n')
}
