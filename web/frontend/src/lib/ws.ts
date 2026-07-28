/**
 * 评审进度 WebSocket 客户端。
 *
 * 为什么需要：一次评审要调数十次 LLM，几十秒到几分钟。
 * 后端 202 立刻返回 review_id，真实进度由这条 WS 推过来。
 *
 * 设计原则（吃过亏之后定的）：
 *   WS 只是「更快知道」的加速器，**不是唯一通道**。
 *   后端 ConnectionManager.broadcast 只推给当前在线连接，无重放无补发——
 *   断线期间的 review.completed 会永久丢失。所以调用方必须常驻兜底轮询，
 *   本模块负责把「连接状态变化」如实汇报出去，让调用方决定轮询快慢与补拉。
 *
 * 本模块提供：
 *   - 指数退避自动重连（网络抖动不该让用户丢进度）
 *   - 终态（completed/failed/cancelled）后不再重连
 *   - onOpen 带 reconnected 标记：重连成功必须补拉一次全量状态
 *   - onStatusChange：connecting / open / reconnecting / unavailable，用于 UI 交代
 */

import type { WsEvent, WsEventName } from './types'
import { getToken } from './apiClient'

type Handler = (event: WsEvent) => void

/** 连接状态。unavailable = 重试耗尽，本次不再自动重连 */
export type WsStatus = 'connecting' | 'open' | 'reconnecting' | 'unavailable' | 'closed'

export interface OpenInfo {
  /** true 表示这次 open 之前已经成功连过一次 —— 期间的事件可能已经丢了，调用方必须补拉 */
  reconnected: boolean
}

export interface ReviewSocketOptions {
  onEvent: Handler
  /** 连接建立。reconnected=true 时调用方必须重新拉一次状态（断线期间事件不会补发） */
  onOpen?: (info: OpenInfo) => void
  onClose?: () => void
  /** 连不上时的兜底：调用方可在这里提高轮询频率 */
  onUnavailable?: () => void
  /** 每次连接状态变化都会回调，用于 UI 如实告诉用户现在是什么情况 */
  onStatusChange?: (status: WsStatus) => void
  maxRetries?: number
}

const TERMINAL: WsEventName[] = ['review.completed', 'review.failed', 'review.cancelled']

export function connectReviewSocket(reviewId: string, opts: ReviewSocketOptions) {
  const { onEvent, onOpen, onClose, onUnavailable, onStatusChange, maxRetries = 5 } = opts

  let ws: WebSocket | null = null
  let retries = 0
  let closedByUs = false
  let everOpened = false
  let timer: ReturnType<typeof setTimeout> | null = null
  let status: WsStatus = 'connecting'

  const setStatus = (next: WsStatus) => {
    if (status === next) return
    status = next
    onStatusChange?.(next)
  }

  const base = (import.meta.env.VITE_API_BASE as string) || window.location.origin
  // 浏览器 WS 不能带自定义 header，token 走查询参数——后端据此校验评审归属
  const token = getToken()
  const wsUrl =
    base.replace(/^http/, 'ws') +
    `/ws/review/${reviewId}` +
    (token ? `?token=${encodeURIComponent(token)}` : '')

  const open = () => {
    if (closedByUs) return
    setStatus(everOpened ? 'reconnecting' : 'connecting')
    try {
      ws = new WebSocket(wsUrl)
    } catch {
      scheduleRetry()
      return
    }

    ws.onopen = () => {
      const reconnected = everOpened
      everOpened = true
      retries = 0
      setStatus('open')
      // 重连场景：断线期间后端推的事件不会补发，调用方必须补拉一次全量
      onOpen?.({ reconnected })
    }

    ws.onmessage = (e) => {
      let payload: WsEvent
      try {
        payload = JSON.parse(e.data)
      } catch {
        return
      }
      onEvent(payload)
      if (TERMINAL.includes(payload.event)) {
        closedByUs = true // 终态：不再重连
        setStatus('closed')
        ws?.close()
      }
    }

    ws.onerror = () => {
      /* onclose 会紧随其后，重连逻辑统一放那里 */
    }

    ws.onclose = () => {
      onClose?.()
      if (!closedByUs) scheduleRetry()
    }
  }

  const scheduleRetry = () => {
    if (closedByUs) return
    if (retries >= maxRetries) {
      setStatus('unavailable')
      onUnavailable?.() // 交给调用方提高轮询频率
      return
    }
    const delay = Math.min(1000 * 2 ** retries, 10_000) // 指数退避，封顶 10s
    retries += 1
    setStatus('reconnecting')
    timer = setTimeout(open, delay)
  }

  open()

  return {
    close() {
      closedByUs = true
      if (timer) clearTimeout(timer)
      setStatus('closed')
      ws?.close()
    },
  }
}
