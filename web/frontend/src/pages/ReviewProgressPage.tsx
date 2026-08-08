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
import { api, claimPendingReviews, getReviewJobId } from '@/lib/apiClient'
import { connectReviewSocket } from '@/lib/ws'
import type { WsStatus } from '@/lib/ws'
import { cn } from '@/lib/utils'
import type { Review, WSMessage, ReviewMode } from '@/lib/mock-data'
import type { ReviewDetail } from '@/lib/types'
import { usePersonaStore } from '@/store/persona-store'
import { ArrowLeft, FileText, DollarSign, Clock, Loader2, CheckCircle2, AlertCircle, Zap, ListChecks, Microscope, Swords, BarChart3, Hourglass } from 'lucide-react'

type PhaseStatus = 'waiting' | 'running' | 'completed'

/** WS 不通时轮询是唯一通道 */
const POLL_FAST_MS = 3000
/** WS 通时的保险丝：只为兜住「连着但事件没送达」，别打爆后端 */
const POLL_SLOW_MS = 15000
/** 多久没有任何进展就向用户交代一句 */
const STALL_HINT_SEC = 45

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '等待中', color: 'text-text-muted', bg: 'bg-status-waiting' },
  running: { label: '运行中', color: 'text-cyan', bg: 'bg-status-running' },
  completed: { label: '已完成', color: 'text-brand-primary', bg: 'bg-status-completed' },
  failed: { label: '失败', color: 'text-severity-critical', bg: 'bg-status-failed' },
  cancelled: { label: '已取消', color: 'text-text-muted', bg: 'bg-status-waiting' },
}

const modeBadgeConfig: Record<ReviewMode, { label: string; color: string; bg: string; Icon: typeof Zap }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', Icon: Zap },
  standard: { label: '标准', color: 'text-brand-primary', bg: 'bg-brand-primary/10', Icon: ListChecks },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', Icon: Microscope },
}

/** 每张人格卡的进度条怎么画。
 *  后端不提供人格粒度的百分比，所以除了 completed 之外没有可展示的真实数字：
 *  · running 以前恒写 50%——一个编出来的数，任务卡死时它也纹丝不动地骗人，
 *    改成不带数字的流光条（「在跑，但说不出跑到哪」如实呈现为不确定态）；
 *  · failed 以前和 completed 一样画满 100%——失败被伪装成「进度圆满」，
 *    现在失败不画进度条，只留下面那行红色的失败说明。 */
function personaBarMode(status: string): 'full' | 'indeterminate' | 'none' {
  if (status === 'completed') return 'full'
  if (status === 'running') return 'indeterminate'
  return 'none'
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
  /** 首次加载失败的真实原因。只在两条链路都拿不到数据时用于区分
   *  「这条评审不存在」和「没能加载出来」——以前两者都渲染成「未找到评审记录」 */
  const [loadError, setLoadError] = useState<Error | null>(null)
  const [crossExamPhase, setCrossExamPhase] = useState<PhaseStatus>('waiting')
  const [aggregationPhase, setAggregationPhase] = useState<PhaseStatus>('waiting')

  // v2 WS 推送的进度信号（v1 链路不会碰这些状态）
  const [v2Progress, setV2Progress] = useState<number | null>(null)
  const [v2Done, setV2Done] = useState(0)
  const [v2Total, setV2Total] = useState(0)
  const [v2CompletedIds, setV2CompletedIds] = useState<string[]>([])
  const [wsError, setWsError] = useState<string | null>(null)

  // WS 连接状态（如实反映给用户，而不是让进度条静止着装死）
  const [wsStatus, setWsStatus] = useState<WsStatus>('connecting')
  // 距上一次「有任何进展」过去多久（秒）。用于超时交代
  const [idleSec, setIdleSec] = useState(0)
  // 连续拉取失败次数（失败不静默吞）
  const [pollFailures, setPollFailures] = useState(0)

  // 轮询兜底用：记住这条评审在哪个 API 上取得到
  const sourceRef = useRef<'v1' | 'v2'>('v1')
  const socketRef = useRef<{ close: () => void } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollIntervalRef = useRef(0)
  const pollFailRef = useRef(0)
  // 0 = 还没记过；下面 activitySig 的 effect 首次渲染就会把它填成 Date.now()
  const lastActivityRef = useRef(0)
  const { personas, initPersonas, initialized } = usePersonaStore()

  useEffect(() => {
    if (!initialized) initPersonas()
  }, [initialized, initPersonas])

  const loadReview = useCallback(async () => {
    if (!id) return

    // v1 优先：数据更全；v2 创建的评审同库同表，v1 端点通常也能取到。
    // v2 这一步的异常**不吞**——外层要靠它决定是否走认领重试。
    const attempt = async () => {
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
      const d = await api.getReview(id)
      setDetail(d)
      sourceRef.current = 'v2'
      if (d.status === 'completed') {
        setCrossExamPhase('completed')
        setAggregationPhase('completed')
      }
    }

    try {
      await attempt()
      setLoadError(null)
    } catch (firstError) {
      // 两条链路都取不到，最常见的原因是"这条评审是匿名跑的，还挂在共享的
      // anonymous 桶里"，而这个浏览器刚拿到独立身份（登录 / 注册 / 兑换 CDK
      // 拿游客 token）——后端按 user_id 精确比对归属，于是立刻 404。
      // 认领一次再重试，写法与 ReportPage 的兜底一致；只修 ReportPage 不修这里
      // 的话，用户从"发起评审→进度页"这条最主要的路径上照样看到"未找到评审记录"。
      let recovered = false
      try {
        const claimed = await claimPendingReviews()
        if (claimed.includes(id)) {
          await attempt()
          recovered = true
        }
      } catch {
        // 认领这条兜底路径自己也失败了（未登录 / 限流 / 后端不支持）。它的失败
        // 原因对用户没有意义——该看到的是下面这个"第一次为什么加载不出来"。
      }
      if (recovered) setLoadError(null)
      else setLoadError(firstError instanceof Error ? firstError : new Error(String(firstError)))
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
    pollIntervalRef.current = 0
  }, [])

  /** 拉一次状态。返回是否已到终态。轮询和「重连补拉」共用这一条路径 */
  const refreshOnce = useCallback(async (): Promise<boolean> => {
    if (!id) return false
    try {
      if (sourceRef.current === 'v2') {
        const d = await api.getReview(id)
        setDetail(d)
        pollFailRef.current = 0
        setPollFailures(0)
        // v2 的百分比进度只有 WS 和 /api/jobs/{job_id} 两个来源。WS 断线时
        // 光靠 getReview 只能拿到状态字段，进度条会停在断线那一刻的数字上。
        // 创建评审时记下的 job_id 在这里补上百分比；查不到映射（换设备 /
        // 清了本地存储）或 job 端点失败都只是维持现状，不算轮询失败。
        const jobId = getReviewJobId(id)
        if (jobId && !isTerminal(d.status)) {
          try {
            const job = await api.getJob(jobId)
            if (typeof job.progress === 'number') {
              setV2Progress(Math.max(0, Math.min(100, Math.round(job.progress))))
            }
          } catch {
            // 拿不到百分比不影响状态轮询这条主链路
          }
        }
        if (d.status === 'completed') {
          setCrossExamPhase('completed')
          setAggregationPhase('completed')
        }
        return isTerminal(d.status)
      }
      const data = await fetchReview(id)
      setReview(data)
      pollFailRef.current = 0
      setPollFailures(0)
      if (data.status === 'completed') {
        setCrossExamPhase('completed')
        setAggregationPhase('completed')
      }
      return isTerminal(data.status)
    } catch {
      // 不静默吞：计数并在界面上如实说「同步失败，正在重试」
      pollFailRef.current += 1
      setPollFailures(pollFailRef.current)
      return false
    }
  }, [id])

  /**
   * 常驻兜底轮询。
   *
   * 为什么不能「WS 通了就停」：后端 broadcast 无重放无补发，
   * WS 连着但事件没送达（事件名不匹配 / 某条代码路径没发 / 半开连接）时，
   * 只靠 WS 会永远停在 pending。所以轮询永远在跑，只有终态才停。
   * WS 通时降到低频（只是保险），WS 不通时提到高频（此时它是唯一通道）。
   */
  const ensurePolling = useCallback(
    (intervalMs: number) => {
      if (!id) return
      if (pollRef.current && pollIntervalRef.current === intervalMs) return
      if (pollRef.current) clearInterval(pollRef.current)
      pollIntervalRef.current = intervalMs
      pollRef.current = setInterval(() => {
        void refreshOnce().then((done) => {
          if (done) stopPolling()
        })
      }, intervalMs)
    },
    [id, refreshOnce, stopPolling],
  )

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

    // 先把兜底开起来：WS 可能一直卡在 connecting（既不 open 也不 close），
    // 那种情况下没有任何回调会触发，只靠回调启动轮询等于没有兜底
    ensurePolling(POLL_FAST_MS)

    // socket.close() 之后浏览器还会异步回一次 onclose —— 那时本 effect 已经
    // 清理过了（终态 / 卸载 / 换 id）。不挡住的话 onClose 会重新 ensurePolling，
    // 造出一个谁也关不掉的 3 秒 interval，在卸载后继续 setState。
    let disposed = false

    const socket = connectReviewSocket(id, {
      onEvent: (payload) => {
        if (disposed) return
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
      onOpen: ({ reconnected }) => {
        if (disposed) return
        // WS 通了也**不停**轮询，只降频：后端 broadcast 无补发，
        // WS 连着但事件没送达时轮询是唯一能到达终态的路径
        ensurePolling(POLL_SLOW_MS)
        // 断线期间推的事件（尤其是 review.completed）永久丢失 → 重连必须补拉一次
        if (reconnected) void refreshOnce().then((done) => { if (done) stopPolling() })
      },
      onStatusChange: (s) => {
        if (disposed) return
        setWsStatus(s)
      },
      // WS 不通时它是唯一通道 → 提到高频
      onUnavailable: () => {
        if (disposed) return
        ensurePolling(POLL_FAST_MS)
      },
      onClose: () => {
        if (disposed) return
        ensurePolling(POLL_FAST_MS)
      },
    })
    socketRef.current = socket
    return () => {
      disposed = true
      socket.close()
      socketRef.current = null
    }
  }, [id, loading, terminal, handleV1Event, handleV2Event, ensurePolling, refreshOnce, stopPolling])

  // 到终态就彻底停：这是轮询唯一的退出条件
  useEffect(() => {
    if (terminal) stopPolling()
  }, [terminal, stopPolling])

  // 「有进展」的指纹：任一进度信号变化就重置计时
  const activitySig = [
    status,
    v2Progress,
    v2Done,
    v2CompletedIds.length,
    crossExamPhase,
    aggregationPhase,
    (review?.persona_outputs ?? []).map((p) => p.status).join(','),
  ].join('|')

  useEffect(() => {
    lastActivityRef.current = Date.now()
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIdleSec(0)
  }, [activitySig])

  // 停滞计时器：很久没动静时界面要说点什么，而不是杵着一个不动的进度条
  useEffect(() => {
    if (terminal || loading) return
    const t = setInterval(() => {
      // 0 = 还没记过基准（正常不会走到，防御一下，别算出一个天文数字的"已停滞 N 秒"）
      if (!lastActivityRef.current) {
        lastActivityRef.current = Date.now()
        return
      }
      setIdleSec(Math.round((Date.now() - lastActivityRef.current) / 1000))
    }, 5000)
    return () => clearInterval(t)
  }, [terminal, loading])

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        <Loader2 className="w-8 h-8 text-cyan animate-spin mx-auto mb-4" strokeWidth={1.25} />
        <p className="text-text-secondary">加载中...</p>
      </div>
    )
  }

  if (!review && !detail) {
    // 「加载失败」和「真的没有这条评审」必须分开说：以前一律显示"未找到评审记录"，
    // 断网 / 500 / 403 全被伪装成"这条评审不存在"，用户会以为数据没了。
    return (
      <div className="max-w-5xl mx-auto px-4 py-16 text-center">
        {loadError ? (
          <>
            <AlertCircle className="w-10 h-10 text-severity-critical mx-auto mb-3" strokeWidth={1.25} />
            <p className="text-text-secondary mb-1">没能加载这条评审</p>
            <p className="text-text-muted text-xs mb-1 break-all">{loadError.message}</p>
            <p className="text-text-muted text-xs mb-5">这不代表评审被删除了，评审仍在后台继续运行</p>
            <button
              onClick={() => {
                setLoading(true)
                void loadReview().finally(() => setLoading(false))
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm text-text-secondary hover:border-brand-primary/30 hover:text-text-primary transition-colors"
            >
              重试
            </button>
          </>
        ) : (
          <p className="text-text-secondary">未找到评审记录</p>
        )}
        <Link to="/history" className="text-cyan hover:text-cyan-dim mt-4 block">返回评审历史</Link>
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

  // 连接 / 停滞提示。优先级：拉取失败 > 实时通道异常 > 长时间无进展
  const connectionNotice: { text: string; tone: 'warn' | 'info' } | null =
    pollFailures >= 2
      ? {
          tone: 'warn',
          text: `无法从服务器同步进度（已连续失败 ${pollFailures} 次），正在自动重试。评审在后台继续运行，不会因此中断。`,
        }
      : wsStatus === 'unavailable'
        ? {
            tone: 'warn',
            text: `实时连接不可用，已切换为每 ${POLL_FAST_MS / 1000} 秒轮询获取进度。进度仍会更新，只是稍慢。`,
          }
        : wsStatus === 'reconnecting'
          ? {
              tone: 'warn',
              text: '实时连接中断，正在重连；期间已切换为轮询获取进度。',
            }
          : idleSec >= STALL_HINT_SEC
            ? {
                tone: 'info',
                text: `已有 ${idleSec} 秒没有新进展 —— 仍在处理中（某个人格的长文本推理可能耗时较久）。页面每 ${
                  (wsStatus === 'open' ? POLL_SLOW_MS : POLL_FAST_MS) / 1000
                } 秒会主动同步一次状态。`,
              }
            : null

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
            className="flex items-center gap-2 px-3 md:px-4 py-2 rounded-lg bg-brand-primary/10 text-brand-primary hover:bg-brand-primary/20 transition-colors text-sm"
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
            className="h-full rounded-full bg-brand-primary transition-all duration-700"
            style={{ width: `${overallProgress}%` }}
          />
        </div>
      </div>

      {/* 连接 / 停滞交代：不动的进度条必须配一句话，否则用户只会读成「卡死」 */}
      {!terminal && connectionNotice && (
        <div
          className={cn(
            'mb-6 rounded-xl border bg-bg-card p-3 flex items-start gap-2.5',
            connectionNotice.tone === 'warn'
              ? 'border-warm-orange/40'
              : 'border-border',
          )}
        >
          <AlertCircle
            className={cn(
              'w-4 h-4 shrink-0 mt-0.5',
              connectionNotice.tone === 'warn' ? 'text-warm-orange' : 'text-text-muted',
            )}
            strokeWidth={1.25}
          />
          <p className="text-xs text-text-secondary">{connectionNotice.text}</p>
        </div>
      )}

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
        <div className="mb-6 rounded-xl border-2 border-brand-primary/30 bg-bg-card p-4 flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-center gap-2 flex-1">
            <CheckCircle2 className="w-5 h-5 text-brand-primary shrink-0" strokeWidth={1.25} />
            <span className="text-sm text-text-primary font-medium">评审已完成，报告已生成</span>
          </div>
          <Link
            to={`/review/${id}/report`}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-primary text-white text-sm font-bold hover:bg-brand-primary-dim transition-colors"
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
              const barMode = personaBarMode(po.status)
              const persona = personas.find((p) => p.id === po.persona_id)
              return (
                <div
                  key={po.persona_id}
                  className={cn(
                    'rounded-xl border-2 p-3 md:p-4 transition-all',
                    'bg-bg-card',
                    po.status === 'completed' ? 'border-brand-primary/20' :
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
                            ? 'border-brand-primary/40 bg-brand-primary/10 text-brand-primary'
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
                    {barMode !== 'none' && (
                      <div
                        className={cn(
                          'flex-1 h-2 bg-bg-secondary rounded-full overflow-hidden',
                          // 只有真在跑的人格才流光；completed 还在流光是错误信号
                          barMode === 'indeterminate' && 'shimmer-bar',
                        )}
                      >
                        <div
                          className={cn(
                            'h-full rounded-full transition-all duration-700',
                            barMode === 'full'
                              ? 'bg-brand-primary'
                              // 不确定态：低透明度铺满配合流光，视觉上是「在动」
                              // 而不是「停在某个具体百分比」
                              : 'bg-cyan/40'
                          )}
                          style={{ width: '100%' }}
                        />
                      </div>
                    )}
                    {/* 只有 completed 才有真实的 100% 可写；running 没有可信数字，不编 */}
                    {barMode === 'full' && (
                      <span className="text-xs font-mono text-text-muted">100%</span>
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
                  className="animate-pop-in rounded-xl border-2 border-brand-primary/20 bg-bg-card p-3 md:p-4 flex items-center gap-2.5"
                >
                  {/* animate-ring-out 的 ::before 依赖这层 relative 定位 */}
                  <div className="animate-ring-out relative shrink-0">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full border border-brand-primary/40 bg-brand-primary/10 text-xs font-semibold text-brand-primary">
                      {(persona?.name ?? pid).slice(0, 1)}
                    </div>
                    <CheckCircle2 className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 text-brand-primary bg-bg-card rounded-full" strokeWidth={2} />
                  </div>
                  <span className="font-medium text-text-primary text-sm truncate">
                    {persona?.name ?? pid}
                  </span>
                  {persona && <span className="text-xs text-text-muted shrink-0">{persona.archetype}</span>}
                  <span className="ml-auto text-xs text-brand-primary shrink-0">已完成</span>
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
                  ? 'text-brand-primary'
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
              className={cn('w-4 h-4 text-brand-primary', !terminal && aggregationPhase === 'waiting' && 'animate-breathe')}
              strokeWidth={1.5}
            />
            <h3 className="text-sm font-medium text-text-primary">聚合分析</h3>
            <span
              className={cn(
                'ml-auto text-xs',
                aggregationPhase === 'completed'
                  ? 'text-brand-primary'
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
                className="h-full bg-brand-primary rounded-full transition-all duration-700"
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
