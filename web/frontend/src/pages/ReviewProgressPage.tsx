/**
 * 评审进度页 —— 同时接住 v1 / v2 两条链路。
 *
 * v1（旧）：/api/reviews/{id} 返回含 persona_outputs 的全量 Review，
 *          WS 消息形如 { type: 'persona_completed', ... }。
 * v2（新）：/api/v2/reviews/{id} 返回精简 ReviewDetail，
 *          WS 事件形如 { event: 'review.progress', data: {...} }。
 *
 * 两套事件在同一个 WS 处理器里按字段判别（event 前缀 vs type），互不干扰。
 * WS 连不上时回落到 2s 轮询（终态自动停止）。
 */
import { useParams, Link } from 'react-router'
import { useState, useEffect, useRef, useCallback } from 'react'
import { fetchReview } from '@/lib/api'
import { api } from '@/lib/apiClient'
import { connectReviewSocket } from '@/lib/ws'
import { cn } from '@/lib/utils'
import type { Review, WSMessage, ReviewMode } from '@/lib/mock-data'
import type { ReviewDetail } from '@/lib/types'
import { usePersonaStore } from '@/store/persona-store'
import { ArrowLeft, FileText, DollarSign, Clock, Loader2, CheckCircle2, AlertCircle, Zap, ListChecks, Microscope, Swords, BarChart3, Hourglass } from 'lucide-react'

type PhaseStatus = 'waiting' | 'running' | 'completed'

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '等待中', color: 'text-text-muted', bg: 'bg-status-waiting' },
  running: { label: '运行中', color: 'text-cyan', bg: 'bg-status-running' },
  completed: { label: '已完成', color: 'text-neon-green', bg: 'bg-status-completed' },
  failed: { label: '失败', color: 'text-severity-critical', bg: 'bg-status-failed' },
  cancelled: { label: '已取消', color: 'text-text-muted', bg: 'bg-status-waiting' },
}

const modeBadgeConfig: Record<ReviewMode, { label: string; color: string; bg: string; Icon: typeof Zap }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', Icon: Zap },
  standard: { label: '标准', color: 'text-neon-green', bg: 'bg-neon-green/10', Icon: ListChecks },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', Icon: Microscope },
}

function getPersonaProgress(status: string): number {
  if (status === 'completed' || status === 'failed') return 100
  if (status === 'running') return 50
  return 0
}

function isTerminal(status: string | null | undefined): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled'
}

export default function ReviewProgressPage() {
  const { id } = useParams()
  // v1 全量数据（含 persona_outputs / target_title）
  const [review, setReview] = useState<Review | null>(null)
  // v2 精简数据（含 error_message / report）
  const [detail, setDetail] = useState<ReviewDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [crossExamPhase, setCrossExamPhase] = useState<PhaseStatus>('waiting')
  const [aggregationPhase, setAggregationPhase] = useState<PhaseStatus>('waiting')

  // v2 WS 推送的进度信号（v1 链路不会碰这些状态）
  const [v2Progress, setV2Progress] = useState<number | null>(null)
  const [v2Done, setV2Done] = useState(0)
  const [v2Total, setV2Total] = useState(0)
  const [v2CompletedIds, setV2CompletedIds] = useState<string[]>([])
  const [wsError, setWsError] = useState<string | null>(null)

  // 轮询兜底用：记住这条评审在哪个 API 上取得到
  const sourceRef = useRef<'v1' | 'v2'>('v1')
  const socketRef = useRef<{ close: () => void } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const { personas, initPersonas, initialized } = usePersonaStore()

  useEffect(() => {
    if (!initialized) initPersonas()
  }, [initialized, initPersonas])

  const loadReview = useCallback(async () => {
    if (!id) return
    // v1 优先：数据更全；v2 创建的评审同库同表，v1 端点通常也能取到
    try {
      const data = await fetchReview(id)
      setReview(data)
      sourceRef.current = 'v1'
      if (data.status === 'completed') {
        setCrossExamPhase('completed')
        setAggregationPhase('completed')
      }
      return
    } catch {
      // 回落 v2
    }
    try {
      const d = await api.getReview(id)
      setDetail(d)
      sourceRef.current = 'v2'
      if (d.status === 'completed') {
        setCrossExamPhase('completed')
        setAggregationPhase('completed')
      }
    } catch {
      // 两条链路都取不到 → 渲染「未找到」
    }
  }, [id])

  useEffect(() => {
    // 挂载时拉取评审数据——数据获取属于合法的 effect 用途
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadReview().finally(() => setLoading(false))
  }, [loadReview])

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  /** WS 彻底连不上时的兜底：2s 轮询，终态停止 */
  const startPolling = useCallback(() => {
    if (!id || pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        if (sourceRef.current === 'v2') {
          const d = await api.getReview(id)
          setDetail(d)
          if (isTerminal(d.status)) {
            if (d.status === 'completed') {
              setCrossExamPhase('completed')
              setAggregationPhase('completed')
            }
            stopPolling()
          }
        } else {
          const data = await fetchReview(id)
          setReview(data)
          if (isTerminal(data.status)) {
            if (data.status === 'completed') {
              setCrossExamPhase('completed')
              setAggregationPhase('completed')
            }
            stopPolling()
          }
        }
      } catch {
        // 网络抖动：下个周期再试
      }
    }, 2000)
  }, [id, stopPolling])

  // 卸载时清掉轮询
  useEffect(() => () => stopPolling(), [stopPolling])

  /** v2 事件：{ event: 'review.*', data: {...} } */
  const handleV2Event = useCallback(
    (event: string, data: Record<string, unknown>) => {
      switch (event) {
        case 'review.started':
          setReview((prev) => (prev ? { ...prev, status: 'running' as const } : prev))
          setDetail((prev) => (prev ? { ...prev, status: 'running' as const } : prev))
          break
        case 'review.progress': {
          const p = typeof data.progress === 'number' ? data.progress : null
          if (p !== null) setV2Progress(Math.max(0, Math.min(100, Math.round(p))))
          break
        }
        case 'review.persona_completed': {
          if (typeof data.done === 'number') setV2Done(data.done)
          if (typeof data.total === 'number') setV2Total(data.total)
          const pid = typeof data.persona_id === 'string' ? data.persona_id : ''
          if (pid) setV2CompletedIds((prev) => (prev.includes(pid) ? prev : [...prev, pid]))
          break
        }
        case 'review.completed':
          setV2Progress(100)
          setCrossExamPhase('completed')
          setAggregationPhase('completed')
          setReview((prev) => (prev ? { ...prev, status: 'completed' as const } : prev))
          setDetail((prev) => (prev ? { ...prev, status: 'completed' as const } : prev))
          stopPolling()
          void loadReview() // 拉全量：报告入口 / 费用
          break
        case 'review.failed': {
          const err = typeof data.error === 'string' ? data.error : null
          setWsError(err)
          setReview((prev) => (prev ? { ...prev, status: 'failed' as const } : prev))
          setDetail((prev) =>
            prev
              ? { ...prev, status: 'failed' as const, error_message: err ?? prev.error_message }
              : prev,
          )
          stopPolling()
          break
        }
      }
    },
    [loadReview, stopPolling],
  )

  /** v1 事件：{ type: 'persona_completed', ... }（保持旧行为不变） */
  const handleV1Event = useCallback(
    (msg: WSMessage) => {
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
          stopPolling()
          void loadReview()
          // v1 终态事件 ws.ts 识别不了，手动关闭以免无谓重连
          socketRef.current?.close()
          break
        case 'review_failed':
          setReview((prev) => prev ? { ...prev, status: 'failed' } : prev)
          if (msg.error) setWsError(msg.error)
          stopPolling()
          socketRef.current?.close()
          break
      }
    },
    [loadReview, stopPolling],
  )

  const status = review?.status ?? detail?.status ?? null
  const terminal = isTerminal(status)

  useEffect(() => {
    if (!id || loading || terminal) return

    const socket = connectReviewSocket(id, {
      onEvent: (payload) => {
        // 同一个处理器接两代事件：v2 有 event 字段，v1 有 type 字段
        const raw = payload as unknown as {
          event?: string
          data?: Record<string, unknown>
          type?: string
        }
        if (typeof raw.event === 'string' && raw.event.startsWith('review.')) {
          handleV2Event(raw.event, raw.data ?? {})
        } else if (typeof raw.type === 'string') {
          handleV1Event(raw as unknown as WSMessage)
        }
      },
      onOpen: () => stopPolling(), // WS 通了就别双通道
      onUnavailable: () => startPolling(), // 重试耗尽 → 轮询兜底
    })
    socketRef.current = socket
    return () => {
      socket.close()
      socketRef.current = null
    }
  }, [id, loading, terminal, handleV1Event, handleV2Event, startPolling, stopPolling])

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <Loader2 className="w-8 h-8 text-cyan animate-spin mx-auto mb-4" strokeWidth={1.25} />
        <p className="text-text-secondary">加载中...</p>
      </div>
    )
  }

  if (!review && !detail) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <p className="text-text-secondary">未找到评审记录</p>
        <Link to="/history" className="text-cyan hover:text-cyan-dim mt-4 inline-block">返回评审历史</Link>
      </div>
    )
  }

  const personaOutputs = review?.persona_outputs ?? []
  const completedCount = personaOutputs.filter((p) => p.status === 'completed').length
  const totalCount = personaOutputs.length

  // v2 链路只有事件流信号，没有 persona_outputs
  const hasV2Signal = v2Progress !== null || v2Total > 0
  const personaDone = totalCount > 0 ? completedCount : v2Done
  const personaTotal = totalCount > 0 ? totalCount : v2Total

  const personaProgress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0
  const crossExamProgress = crossExamPhase === 'completed' ? 100 : crossExamPhase === 'running' ? 50 : 0
  const aggregationProgress = aggregationPhase === 'completed' ? 100 : aggregationPhase === 'running' ? 50 : 0
  const overallProgress =
    status === 'completed'
      ? 100
      : hasV2Signal
        ? (v2Progress ?? Math.round((v2Done / Math.max(v2Total, 1)) * 80))
        : Math.round(personaProgress * 0.7 + crossExamProgress * 0.15 + aggregationProgress * 0.15)

  const title = review?.target_title || detail?.task_type || '评审'
  const costUsd = review?.total_cost_usd ?? detail?.total_cost_usd ?? 0
  const errorMessage = wsError ?? detail?.error_message ?? null
  const sc = statusConfig[status ?? 'pending'] ?? statusConfig.pending

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 animate-fade-in">
      <div className="flex items-center gap-3 mb-6">
        <Link to="/history" className="p-2 rounded-lg hover:bg-bg-card transition-colors">
          <ArrowLeft className="w-5 h-5 text-text-secondary" strokeWidth={1.25} />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-semibold text-text-primary truncate">{title}</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-text-secondary">评审进度</p>
            {(() => {
              const reviewMode = (review?.mode ?? detail?.mode ?? 'standard') as ReviewMode
              const mb = modeBadgeConfig[reviewMode] ?? modeBadgeConfig.standard
              return (
                <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium', mb.bg, mb.color)}>
                  <mb.Icon className="w-3 h-3" strokeWidth={1.5} />
                  {mb.label}
                </span>
              )
            })()}
            {detail?.skill_type && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-cyan/10 text-cyan">
                技能 · {detail.skill_type === 'red_team_audience' ? '红队受众' : detail.skill_type === 'audience_panel' ? '受众面板' : detail.skill_type}
              </span>
            )}
            {detail?.selected_personas && detail.selected_personas.length > 0 && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-cyan/10 text-cyan">
                指定角色 · {detail.selected_personas.length} 位
              </span>
            )}
            {detail?.project_key && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-warm-orange/10 text-warm-orange">
                项目 · {detail.project_key}
              </span>
            )}
          </div>
        </div>
        {status === 'completed' && (
          <Link
            to={`/review/${id}/report`}
            className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg bg-neon-green/10 text-neon-green hover:bg-neon-green/20 transition-colors text-sm"
          >
            <FileText className="w-4 h-4" strokeWidth={1.25} />
            <span className="hidden sm:inline">查看报告</span>
          </Link>
        )}
      </div>

      {/* 总进度条：与对话评审页同一套金色视觉语言 */}
      <div className="mb-6">
        <div className="flex items-center justify-between text-xs mb-1.5">
          <span className="text-text-muted">总进度</span>
          <span className="font-medium text-text-secondary">{overallProgress}%</span>
        </div>
        {/* 跑批时百分比会在某个人格思考时卡住十几秒，静止的条会被读成「卡死」→ 非终态挂流光 */}
        <div className={cn('h-2 overflow-hidden rounded-full bg-bg-card', !terminal && 'shimmer-bar')}>
          <div
            className="h-full rounded-full bg-neon-green transition-all duration-700"
            style={{ width: `${overallProgress}%` }}
          />
        </div>
      </div>

      {/* 失败：如实展示 error_message */}
      {status === 'failed' && (
        <div className="mb-6 rounded-xl border-2 border-severity-critical/30 bg-bg-card p-4 flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 text-severity-critical shrink-0 mt-0.5" strokeWidth={1.25} />
          <div className="min-w-0">
            <p className="text-sm font-medium text-severity-critical">评审失败</p>
            <p className="text-xs text-text-secondary mt-1 break-all">
              {errorMessage ?? '执行失败，请稍后重试'}
            </p>
          </div>
        </div>
      )}

      {/* 完成：报告入口横幅（v2 链路没有其它入口时尤其重要） */}
      {status === 'completed' && (
        <div className="mb-6 rounded-xl border-2 border-neon-green/30 bg-bg-card p-4 flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-center gap-2 flex-1">
            <CheckCircle2 className="w-5 h-5 text-neon-green shrink-0" strokeWidth={1.25} />
            <span className="text-sm text-text-primary font-medium">评审已完成，报告已生成</span>
          </div>
          <Link
            to={`/review/${id}/report`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-neon-green text-bg-primary text-sm font-bold hover:bg-neon-green-dim transition-colors"
          >
            <FileText className="w-4 h-4" strokeWidth={1.25} />
            查看完整报告 →
          </Link>
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <div className="rounded-xl border border-border bg-bg-card p-3 md:p-4">
          <div className="flex items-center gap-2 text-text-muted mb-1">
            <Clock className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="text-xs">状态</span>
          </div>
          <span className={cn('font-medium text-sm', sc.color)}>{sc.label}</span>
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
            {personaDone}/{personaTotal}
          </span>
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-3 md:p-4">
          <div className="flex items-center gap-2 text-text-muted mb-1">
            <DollarSign className="w-3.5 h-3.5" strokeWidth={1.25} />
            <span className="text-xs">已消耗</span>
          </div>
          <span className="font-display font-bold text-warm-orange text-sm md:text-base">${costUsd.toFixed(2)}</span>
        </div>
      </div>

      {/* v2 链路：事件流没带 persona_outputs 时，用总进度条 + 逐人格打勾展示 */}
      {totalCount === 0 && !terminal && (
        <div className="mb-8 rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <div className="flex items-center gap-2 mb-3">
            <Hourglass className="w-4 h-4 text-cyan" strokeWidth={1.5} />
            <h3 className="text-sm font-medium text-text-primary">评审进行中</h3>
          </div>
          <div className="flex items-center gap-3">
            {/* 本分支只在非终态渲染，恒挂流光 */}
            <div className="shimmer-bar flex-1 h-3 bg-bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-cyan rounded-full transition-all duration-700"
                style={{ width: `${overallProgress}%` }}
              />
            </div>
            <span className="font-mono text-sm text-text-secondary">{overallProgress}%</span>
          </div>
          {/* 上方进度条已经在流光传达「没卡死」，这里再转一个 spinner 是重复噪音，
              改成整行呼吸：同样在动，但安静得多 */}
          {!hasV2Signal && (
            <p className="animate-breathe text-xs text-text-muted mt-3 flex items-center gap-1.5">
              <Hourglass className="w-3 h-3" strokeWidth={1.25} />
              等待评审团就位…
            </p>
          )}
        </div>
      )}

      <div className="mb-8">
        <h2 className="text-lg font-semibold text-text-primary mb-4">角色进度</h2>
        {totalCount > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {personaOutputs.map((po) => {
              const psc = statusConfig[po.status] ?? statusConfig.pending
              const progress = getPersonaProgress(po.status)
              const persona = personas.find((p) => p.id === po.persona_id)
              return (
                <div
                  key={po.persona_id}
                  className={cn(
                    'rounded-xl border-2 p-3 md:p-4 transition-all',
                    'bg-bg-card',
                    po.status === 'completed' ? 'border-neon-green/20' :
                    po.status === 'running' ? 'border-cyan/20' : 'border-border',
                    // 「一位人格交卷」是离散事件，给个落点脉冲
                    po.status === 'completed' && 'animate-pop-in',
                  )}
                >
                  <div className="flex items-center gap-2.5 mb-3">
                    {/* 人格头像：与对话评审页同一套圆形身份标识语言 */}
                    <div className="relative shrink-0">
                      <div
                        className={cn(
                          'flex h-8 w-8 items-center justify-center rounded-full border text-xs font-semibold',
                          po.status === 'completed'
                            ? 'border-neon-green/40 bg-neon-green/10 text-neon-green'
                            : po.status === 'running'
                              ? 'border-cyan/40 bg-cyan/10 text-cyan'
                              : po.status === 'failed'
                                ? 'border-severity-critical/40 bg-severity-critical/10 text-severity-critical'
                                : 'border-border bg-bg-secondary text-text-muted',
                        )}
                      >
                        {(po.persona_name ?? '?').slice(0, 1)}
                      </div>
                      <div
                        className={cn(
                          'absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-bg-card',
                          psc.bg,
                          po.status === 'running' && 'animate-pulse-glow',
                        )}
                      />
                    </div>
                    <span className="font-medium text-text-primary text-sm">{po.persona_name}</span>
                    {persona && <span className="text-xs text-text-muted">{persona.archetype}</span>}
                  </div>

                  <div className="flex items-center gap-2 mb-2">
                    <span className={cn('text-xs', psc.color)}>{psc.label}</span>
                    {po.status !== 'pending' && (
                      <div
                        className={cn(
                          'flex-1 h-2 bg-bg-secondary rounded-full overflow-hidden',
                          // 只有真在跑的人格才流光；completed 还在流光是错误信号
                          po.status === 'running' && 'shimmer-bar',
                        )}
                      >
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
        ) : v2CompletedIds.length > 0 || v2Total > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* v2：逐人格打勾（事件只告诉我们谁完成了） */}
            {v2CompletedIds.map((pid) => {
              const persona = personas.find((p) => p.id === pid)
              // 卡片是随 WS 事件一个个 push 进来的，天然适合入场脉冲
              return (
                <div
                  key={pid}
                  className="animate-pop-in rounded-xl border-2 border-neon-green/20 bg-bg-card p-3 md:p-4 flex items-center gap-2.5"
                >
                  {/* animate-ring-out 的 ::before 依赖这层 relative 定位 */}
                  <div className="animate-ring-out relative shrink-0">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full border border-neon-green/40 bg-neon-green/10 text-xs font-semibold text-neon-green">
                      {(persona?.name ?? pid).slice(0, 1)}
                    </div>
                    <CheckCircle2 className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 text-neon-green bg-bg-card rounded-full" strokeWidth={2} />
                  </div>
                  <span className="font-medium text-text-primary text-sm truncate">
                    {persona?.name ?? pid}
                  </span>
                  {persona && <span className="text-xs text-text-muted shrink-0">{persona.archetype}</span>}
                  <span className="ml-auto text-xs text-neon-green shrink-0">已完成</span>
                </div>
              )
            })}
            {!terminal && v2Total > v2CompletedIds.length && (
              <div className="rounded-xl border-2 border-border bg-bg-card p-3 md:p-4 flex items-center gap-2.5">
                <Loader2 className="w-4 h-4 text-cyan animate-spin shrink-0" strokeWidth={1.25} />
                <span className="text-sm text-text-secondary">
                  还有 {v2Total - v2CompletedIds.length} 位人格评审中…
                </span>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-text-muted">
            {terminal ? '本次评审没有可展示的角色明细' : '评审团正在开庭，人格完成后逐一亮灯…'}
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <div className="flex items-center gap-2 mb-3">
            {/* 排队中也给点生命感；running 已有流光，别两个动效打架 */}
            <Swords
              className={cn('w-4 h-4 text-warm-orange', !terminal && crossExamPhase === 'waiting' && 'animate-breathe')}
              strokeWidth={1.5}
            />
            <h3 className="text-sm font-medium text-text-primary">交叉质询</h3>
            <span
              className={cn(
                'ml-auto text-xs',
                crossExamPhase === 'completed'
                  ? 'text-neon-green'
                  : crossExamPhase === 'running'
                    ? 'text-cyan'
                    : 'text-text-muted',
              )}
            >
              {crossExamPhase === 'completed' ? '已完成' : crossExamPhase === 'running' ? '进行中' : '等待中'}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'flex-1 h-3 bg-bg-secondary rounded-full overflow-hidden',
                // !terminal 是必须的：评审在交叉质询中途失败时 phase 会停在 running，
                // 光看 phase 会让终态的条一直流光 = 骗用户「还在跑」
                !terminal && crossExamPhase === 'running' && 'shimmer-bar',
              )}
            >
              <div
                className="h-full bg-warm-orange rounded-full transition-all duration-700"
                style={{ width: `${crossExamProgress}%` }}
              />
            </div>
            <span className="font-mono text-sm text-text-secondary">{crossExamProgress}%</span>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3
              className={cn('w-4 h-4 text-neon-green', !terminal && aggregationPhase === 'waiting' && 'animate-breathe')}
              strokeWidth={1.5}
            />
            <h3 className="text-sm font-medium text-text-primary">聚合分析</h3>
            <span
              className={cn(
                'ml-auto text-xs',
                aggregationPhase === 'completed'
                  ? 'text-neon-green'
                  : aggregationPhase === 'running'
                    ? 'text-cyan'
                    : 'text-text-muted',
              )}
            >
              {aggregationPhase === 'completed' ? '已完成' : aggregationPhase === 'running' ? '进行中' : '等待中'}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'flex-1 h-3 bg-bg-secondary rounded-full overflow-hidden',
                !terminal && aggregationPhase === 'running' && 'shimmer-bar',
              )}
            >
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
