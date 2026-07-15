import { useParams, Link } from 'react-router'
import { useState, useEffect } from 'react'
import { fetchReview, fetchEvaluation, fetchEthicsReport } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { Review, EvaluationScorecard, EthicsReport } from '@/lib/mock-data'
import { EVALUATION_DIMENSIONS, SKILLS } from '@/lib/mock-data'
import { ArrowLeft, ChevronDown, ChevronUp, AlertOctagon, FlaskConical, Shield, Loader2, Clock, User } from 'lucide-react'
import { ResponsiveContainer, Tooltip, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts'

export default function EvaluationPage() {
  const { id } = useParams()
  const [review, setReview] = useState<Review | null>(null)
  const [scorecard, setScorecard] = useState<EvaluationScorecard | null>(null)
  const [ethicsData, setEthicsData] = useState<EthicsReport[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedDimensions, setExpandedDimensions] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (!id) return
    const loadData = async () => {
      try {
        const [reviewData, scorecardData, ethicsResult] = await Promise.all([
          fetchReview(id),
          fetchEvaluation(id),
          fetchEthicsReport(id),
        ])
        setReview(reviewData)
        setScorecard(scorecardData)
        setEthicsData(ethicsResult)
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [id])

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-16 text-center">
        <Loader2 className="w-8 h-8 text-cyan animate-spin mx-auto mb-4" strokeWidth={1.25} />
        <p className="text-text-secondary">加载评估报告...</p>
      </div>
    )
  }

  if (!review || !scorecard) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-16 text-center">
        <FlaskConical className="w-10 h-10 text-text-muted mx-auto mb-4" strokeWidth={1.25} />
        <p className="text-text-secondary mb-2">评估报告尚未生成</p>
        <p className="text-text-muted text-sm mb-6">请先在评审报告页运行评估</p>
        <Link
          to={`/review/${id}/report`}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cyan/10 text-cyan border border-cyan/30 hover:bg-cyan/20 transition-all text-sm"
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.25} />
          返回评审报告
        </Link>
      </div>
    )
  }

  const skill = review.skill_type ? SKILLS.find((s) => s.type === review.skill_type) : null

  const radarData = scorecard.results.map((r) => {
    const dim = EVALUATION_DIMENSIONS.find((d) => d.id === r.dimension)
    return {
      dimension: dim?.name ?? r.dimension,
      score: r.score,
      fullMark: 100,
    }
  })

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 animate-fade-in">
      <div className="flex items-center gap-3 mb-6">
        <Link to={`/review/${id}/report`} className="p-2 rounded-lg hover:bg-bg-card transition-colors">
          <ArrowLeft className="w-5 h-5 text-text-secondary" strokeWidth={1.25} />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold text-text-primary truncate">评估报告</h1>
          <p className="text-sm text-text-secondary">{review.target_title}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-1 rounded-xl border border-border bg-bg-card p-6 flex flex-col items-center justify-center">
          <h3 className="text-sm font-medium text-text-muted mb-4">总体评分</h3>
          <div className={cn(
            'w-28 h-28 rounded-full flex items-center justify-center border-4 mb-4',
            scorecard.overall_score > 70
              ? 'border-neon-green bg-neon-green/10'
              : scorecard.overall_score >= 50
                ? 'border-severity-medium bg-severity-medium/10'
                : 'border-severity-critical bg-severity-critical/10'
          )}>
            <span className={cn(
              'text-3xl font-bold font-mono',
              scorecard.overall_score > 70
                ? 'text-neon-green'
                : scorecard.overall_score >= 50
                  ? 'text-severity-medium'
                  : 'text-severity-critical'
            )}>
              {scorecard.overall_score}
            </span>
          </div>
          <span className={cn(
            'inline-flex items-center gap-1 px-4 py-1.5 rounded-full text-sm font-medium',
            scorecard.passed
              ? 'bg-neon-green/10 text-neon-green'
              : 'bg-severity-critical/10 text-severity-critical'
          )}>
            {scorecard.passed ? '✅ 评估通过' : '❌ 评估未通过'}
          </span>
          <p className="text-xs text-text-muted mt-2">
            {scorecard.results.filter((r) => r.passed).length}/{scorecard.results.length} 维度通过
          </p>
        </div>

        <div className="lg:col-span-2 rounded-xl border border-border bg-bg-card p-6">
          <h3 className="text-sm font-medium text-text-muted mb-4">维度雷达图</h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="var(--color-border)" />
              <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }} />
              <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9, fill: 'var(--color-text-muted)' }} />
              <Radar
                name="评分"
                dataKey="score"
                stroke="var(--color-neon-green)"
                fill="var(--color-neon-green)"
                fillOpacity={0.2}
                strokeWidth={2}
              />
              <Tooltip
                contentStyle={{ backgroundColor: 'var(--color-bg-card)', border: '1px solid var(--color-border)', borderRadius: '8px', fontSize: '12px' }}
                itemStyle={{ color: 'var(--color-text-primary)' }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {scorecard.critical_failures.length > 0 && (
        <div className="rounded-xl border-2 border-severity-critical/30 bg-severity-critical/5 p-4 md:p-5 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <AlertOctagon className="w-5 h-5 text-severity-critical" strokeWidth={1.25} />
            <h3 className="text-base font-semibold text-severity-critical">关键失败项</h3>
          </div>
          <ul className="space-y-2">
            {scorecard.critical_failures.map((cf, i) => (
              <li key={i} className="text-sm text-text-secondary flex items-start gap-2">
                <span className="text-severity-critical font-bold shrink-0">{i + 1}.</span>
                {cf}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mb-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">维度详情</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {scorecard.results.map((result) => {
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
                  className="w-full flex items-center gap-3 px-4 py-4 text-left hover:bg-bg-card-hover transition-colors"
                >
                  <div className={cn(
                    'w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold font-mono',
                    result.passed ? 'bg-neon-green/10 text-neon-green' : 'bg-severity-critical/10 text-severity-critical'
                  )}>
                    {result.score}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-text-primary">{dim?.name ?? result.dimension}</span>
                      <span className={cn(
                        'text-xs px-1.5 py-0.5 rounded',
                        result.passed ? 'bg-neon-green/10 text-neon-green' : 'bg-severity-critical/10 text-severity-critical'
                      )}>
                        {result.passed ? '通过' : '未通过'}
                      </span>
                    </div>
                    <p className="text-xs text-text-muted mt-0.5 line-clamp-1">{dim?.description}</p>
                  </div>
                  {expanded ? (
                    <ChevronUp className="w-4 h-4 text-text-muted shrink-0" strokeWidth={1.25} />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-text-muted shrink-0" strokeWidth={1.25} />
                  )}
                </button>
                {expanded && (
                  <div className="px-4 pb-4 border-t border-border pt-3">
                    <p className="text-xs text-text-muted mb-2">{dim?.description}</p>
                    <p className="text-sm text-text-secondary leading-relaxed">{result.details}</p>
                    <div className="mt-3">
                      <div className="flex items-center justify-between text-xs text-text-muted mb-1">
                        <span>评分</span>
                        <span className={cn(
                          'font-mono font-bold',
                          result.score > 70 ? 'text-neon-green' : result.score >= 50 ? 'text-severity-medium' : 'text-severity-critical'
                        )}>
                          {result.score}/100
                        </span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-bg-secondary overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            result.score > 70 ? 'bg-neon-green' : result.score >= 50 ? 'bg-severity-medium' : 'bg-severity-critical'
                          )}
                          style={{ width: `${result.score}%` }}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {ethicsData.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-violet-700" strokeWidth={1.25} />
            <h3 className="text-lg font-semibold text-text-primary">伦理摘要</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {ethicsData.map((er) => (
              <div key={er.persona_id} className="rounded-xl border border-border bg-bg-card p-4">
                <div className="flex items-center gap-2 mb-3">
                  <User className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                  <span className="text-sm font-medium text-text-primary">{er.persona_id}</span>
                  <span className={cn(
                    'ml-auto text-xs px-2 py-0.5 rounded font-medium',
                    er.passed ? 'bg-neon-green/10 text-neon-green' : 'bg-severity-critical/10 text-severity-critical'
                  )}>
                    {er.passed ? '通过' : '未通过'}
                  </span>
                </div>
                <div className="space-y-2">
                  <div>
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
                          'h-full rounded-full',
                          er.score > 70 ? 'bg-neon-green' : er.score >= 50 ? 'bg-severity-medium' : 'bg-severity-critical'
                        )}
                        style={{ width: `${er.score}%` }}
                      />
                    </div>
                  </div>
                  <div>
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
                          'h-full rounded-full',
                          er.stereotype_risk < 0.3 ? 'bg-neon-green' : er.stereotype_risk < 0.6 ? 'bg-severity-medium' : 'bg-severity-critical'
                        )}
                        style={{ width: `${er.stereotype_risk * 100}%` }}
                      />
                    </div>
                  </div>
                  {er.violations.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {er.violations.map((v, i) => (
                        <span key={i} className="px-1.5 py-0.5 rounded text-[10px] bg-severity-critical/10 text-severity-critical">
                          {v}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
        <div className="flex items-center gap-2 mb-3">
          <Clock className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
          <h3 className="text-sm font-medium text-text-muted">评估时间线</h3>
        </div>
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="text-text-secondary">评审创建</span>
            <span className="text-text-muted font-mono text-xs">{new Date(review.created_at).toLocaleString('zh-CN')}</span>
          </div>
          {review.completed_at && (
            <div className="flex items-center gap-2">
              <span className="text-text-secondary">评审完成</span>
              <span className="text-text-muted font-mono text-xs">{new Date(review.completed_at).toLocaleString('zh-CN')}</span>
            </div>
          )}
          {skill && (
            <div className="flex items-center gap-2">
              <span className="text-text-secondary">使用技能</span>
              <span className={cn('text-xs', skill.color)}>{skill.icon} {skill.name}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
