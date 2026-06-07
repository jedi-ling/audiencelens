import { useParams, Link } from 'react-router'
import { useState, useEffect, useRef, useCallback } from 'react'
import { fetchReview, connectReviewWS } from '@/lib/api'
import { cn } from '@/lib/utils'
import type { Review, WSMessage, ReviewMode } from '@/lib/mock-data'
import { usePersonaStore } from '@/store/persona-store'
import { ArrowLeft, FileText, DollarSign, Clock, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'

type PhaseStatus = 'waiting' | 'running' | 'completed'

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '等待中', color: 'text-text-muted', bg: 'bg-status-waiting' },
  running: { label: '运行中', color: 'text-cyan', bg: 'bg-status-running' },
  completed: { label: '已完成', color: 'text-neon-green', bg: 'bg-status-completed' },
  failed: { label: '失败', color: 'text-severity-critical', bg: 'bg-status-failed' },
}

const modeBadgeConfig: Record<ReviewMode, { label: string; color: string; bg: string; icon: string }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', icon: '⚡' },
  standard: { label: '标准', color: 'text-neon-green', bg: 'bg-neon-green/10', icon: '✅' },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', icon: '🔬' },
}

function getPersonaProgress(status: string): number {
  if (status === 'completed' || status === 'failed') return 100
  if (status === 'running') return 50
  return 0
}

export default function ReviewProgressPage() {
  const { id } = useParams()
  const [review, setReview] = useState<Review | null>(null)
  const [loading, setLoading] = useState(true)
  const [crossExamPhase, setCrossExamPhase] = useState<PhaseStatus>('waiting')
  const [aggregationPhase, setAggregationPhase] = useState<PhaseStatus>('waiting')
  const wsCleanupRef = useRef<(() => void) | null>(null)
  const { personas, initPersonas, initialized } = usePersonaStore()

  useEffect(() => {
    if (!initialized) initPersonas()
  }, [initialized, initPersonas])

  const loadReview = useCallback(async () => {
    if (!id) return
    try {
      const data = await fetchReview(id)
      setReview(data)
      if (data.status === 'completed') {
        setCrossExamPhase('completed')
        setAggregationPhase('completed')
      }
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    loadReview()
  }, [loadReview])

  useEffect(() => {
    if (!id || !review) return
    if (review.status === 'completed' || review.status === 'failed') return

    const cleanup = connectReviewWS(id, (msg: WSMessage) => {
      switch (msg.type) {
        case 'persona_started':
          setReview((prev) => prev ? {
            ...prev,
            status: 'running',
            persona_outputs: prev.persona_outputs.map((po) =>
              po.persona_id === msg.persona_id ? { ...po, status: 'running' as const, started_at: new Date().toISOString() } : po
            ),
          } : prev)
          break
        case 'persona_completed':
          setReview((prev) => prev ? {
            ...prev,
            persona_outputs: prev.persona_outputs.map((po) =>
              po.persona_id === msg.persona_id ? { ...po, status: 'completed' as const, cost_usd: msg.cost_usd ?? po.cost_usd, completed_at: new Date().toISOString() } : po
            ),
            total_cost_usd: prev.total_cost_usd + (msg.cost_usd ?? 0),
          } : prev)
          break
        case 'persona_failed':
          setReview((prev) => prev ? {
            ...prev,
            persona_outputs: prev.persona_outputs.map((po) =>
              po.persona_id === msg.persona_id ? { ...po, status: 'failed' as const, completed_at: new Date().toISOString() } : po
            ),
          } : prev)
          break
        case 'cross_exam_started':
          setCrossExamPhase('running')
          break
        case 'cross_exam_completed':
          setCrossExamPhase('completed')
          break
        case 'aggregation_started':
          setAggregationPhase('running')
          break
        case 'aggregation_completed':
          setAggregationPhase('completed')
          break
        case 'review_completed':
          setReview((prev) => prev ? { ...prev, status: 'completed' } : prev)
          loadReview()
          break
        case 'review_failed':
          setReview((prev) => prev ? { ...prev, status: 'failed' } : prev)
          break
      }
    })

    wsCleanupRef.current = cleanup
    return () => {
      cleanup()
    }
  }, [id, review?.status, loadReview])

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <Loader2 className="w-8 h-8 text-cyan animate-spin mx-auto mb-4" strokeWidth={1.25} />
        <p className="text-text-secondary">加载中...</p>
      </div>
    )
  }

  if (!review) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <p className="text-text-secondary">未找到评审记录</p>
        <Link to="/" className="text-cyan hover:text-cyan-dim mt-4 inline-block">返回首页</Link>
      </div>
    )
  }

  const completedCount = review.persona_outputs.filter((p) => p.status === 'completed').length
  const totalCount = review.persona_outputs.length
  const personaProgress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0
  const crossExamProgress = crossExamPhase === 'completed' ? 100 : crossExamPhase === 'running' ? 50 : 0
  const aggregationProgress = aggregationPhase === 'completed' ? 100 : aggregationPhase === 'running' ? 50 : 0
  const overallProgress = Math.round(personaProgress * 0.7 + crossExamProgress * 0.15 + aggregationProgress * 0.15)

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 animate-fade-in">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/" className="p-2 rounded-lg hover:bg-bg-card transition-colors">
          <ArrowLeft className="w-5 h-5 text-text-secondary" strokeWidth={1.25} />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold text-text-primary truncate">{review.target_title}</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-text-secondary">评审进度</p>
            {(() => {
              const reviewMode = (review.mode ?? 'standard') as ReviewMode
              const mb = modeBadgeConfig[reviewMode] ?? modeBadgeConfig.standard
              return (
                <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', mb.bg, mb.color)}>
                  <span>{mb.icon}</span>
                  {mb.label}
                </span>
              )
            })()}
          </div>
        </div>
        {review.status === 'completed' && (
          <Link
            to={`/review/${review.id}/report`}
            className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg bg-neon-green/10 text-neon-green hover:bg-neon-green/20 transition-colors text-sm"
          >
            <FileText className="w-4 h-4" strokeWidth={1.25} />
            <span className="hidden sm:inline">查看报告</span>
          </Link>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <div className="rounded-xl border border-border bg-bg-card p-3 md:p-4">
          <div className="flex items-center gap-2 text-text-muted mb-1">
            <Clock className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="text-xs">状态</span>
          </div>
          <span className={cn(
            'font-medium text-sm',
            review.status === 'completed' ? 'text-neon-green' :
            review.status === 'running' ? 'text-cyan' : 'text-text-secondary'
          )}>
            {review.status === 'pending' ? '等待中' : review.status === 'running' ? '运行中' : review.status === 'completed' ? '已完成' : '失败'}
          </span>
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-3 md:p-4">
          <div className="flex items-center gap-2 text-text-muted mb-1">
            <Loader2 className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="text-xs">总进度</span>
          </div>
          <span className="font-display font-bold text-cyan text-sm md:text-base">{overallProgress}%</span>
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-3 md:p-4">
          <div className="flex items-center gap-2 text-text-muted mb-1">
            <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="text-xs">角色数</span>
          </div>
          <span className="font-display font-bold text-text-primary text-sm md:text-base">
            {completedCount}/{totalCount}
          </span>
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-3 md:p-4">
          <div className="flex items-center gap-2 text-text-muted mb-1">
            <DollarSign className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="text-xs">已消耗</span>
          </div>
          <span className="font-display font-bold text-warm-orange text-sm md:text-base">${review.total_cost_usd.toFixed(2)}</span>
        </div>
      </div>

      <div className="mb-8">
        <h2 className="text-lg font-semibold text-text-primary mb-4">角色进度</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {review.persona_outputs.map((po) => {
            const sc = statusConfig[po.status] ?? statusConfig.pending
            const progress = getPersonaProgress(po.status)
            const persona = personas.find((p) => p.id === po.persona_id)
            return (
              <div
                key={po.persona_id}
                className={cn(
                  'rounded-xl border-2 p-3 md:p-4 transition-all',
                  'bg-bg-card',
                  po.status === 'completed' ? 'border-neon-green/20' :
                  po.status === 'running' ? 'border-cyan/20' : 'border-border'
                )}
              >
                <div className="flex items-center gap-2 mb-3">
                  <div className={cn('w-2.5 h-2.5 rounded-full', sc.bg, po.status === 'running' && 'animate-pulse-glow')} />
                  <span className="font-medium text-text-primary text-sm">{po.persona_name}</span>
                  {persona && <span className="text-xs text-text-muted">{persona.archetype}</span>}
                </div>

                <div className="flex items-center gap-2 mb-2">
                  <span className={cn('text-xs', sc.color)}>{sc.label}</span>
                  {po.status !== 'pending' && (
                    <div className="flex-1 h-2 bg-bg-secondary rounded-full overflow-hidden">
                      <div
                        className={cn(
                          'h-full rounded-full transition-all duration-700',
                          po.status === 'completed' ? 'bg-neon-green' : 'bg-cyan'
                        )}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  )}
                  {po.status !== 'pending' && (
                    <span className="text-xs font-mono text-text-muted">{progress}%</span>
                  )}
                </div>

                {po.status === 'completed' && po.cost_usd > 0 && (
                  <div className="flex items-center gap-3 text-xs mt-2 pt-2 border-t border-border">
                    <span className="text-text-muted font-mono">
                      费用 ${po.cost_usd.toFixed(3)}
                    </span>
                  </div>
                )}

                {po.status === 'failed' && (
                  <p className="text-xs text-severity-critical mt-1.5 flex items-start gap-1">
                    <AlertCircle className="w-3 h-3 shrink-0 mt-0.5" strokeWidth={1.25} />
                    执行失败
                  </p>
                )}
              </div>
            )
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <h3 className="text-sm font-medium text-text-muted mb-3">交叉质询</h3>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-3 bg-bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-warm-orange rounded-full transition-all duration-700"
                style={{ width: `${crossExamProgress}%` }}
              />
            </div>
            <span className="font-mono text-sm text-text-secondary">{crossExamProgress}%</span>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <h3 className="text-sm font-medium text-text-muted mb-3">聚合分析</h3>
          <div className="flex items-center gap-3">
            <div className="flex-1 h-3 bg-bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-neon-green rounded-full transition-all duration-700"
                style={{ width: `${aggregationProgress}%` }}
              />
            </div>
            <span className="font-mono text-sm text-text-secondary">{aggregationProgress}%</span>
          </div>
        </div>
      </div>
    </div>
  )
}
