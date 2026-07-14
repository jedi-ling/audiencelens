/**
 * 评审进度 WebSocket 客户端。
 *
 * 为什么需要：一次评审要调数十次 LLM，几十秒到几分钟。
 * 后端 202 立刻返回 review_id，真实进度由这条 WS 推过来。
 *
 * 已埋好的健壮性：
 *   - 指数退避自动重连（网络抖动不该让用户丢进度）
 *   - 终态（completed/failed）后不再重连
 *   - 兜底轮询：WS 始终连不上时，调用方可回落到 api.getReview 轮询
 */

import type { WsEvent, WsEventName } from './types'

type Handler = (event: WsEvent) => void

export interface ReviewSocketOptions {
  onEvent: Handler
  onOpen?: () => void
  onClose?: () => void
  /** 连不上时的兜底：调用方可在这里启动轮询 */
  onUnavailable?: () => void
  maxRetries?: number
}

const TERMINAL: WsEventName[] = ['review.completed', 'review.failed']

export function connectReviewSocket(reviewId: string, opts: ReviewSocketOptions) {
  const { onEvent, onOpen, onClose, onUnavailable, maxRetries = 5 } = opts

  let ws: WebSocket | null = null
  let retries = 0
  let closedByUs = false
  let timer: ReturnType<typeof setTimeout> | null = null

  const base = (import.meta.env.VITE_API_BASE as string) || window.location.origin
  const wsUrl = base.replace(/^http/, 'ws') + `/ws/review/${reviewId}`

  const open = () => {
    if (closedByUs) return
    try {
      ws = new WebSocket(wsUrl)
    } catch {
      scheduleRetry()
      return
    }

    ws.onopen = () => {
      retries = 0
      onOpen?.()
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
      onUnavailable?.() // 交给调用方回落轮询
      return
    }
    const delay = Math.min(1000 * 2 ** retries, 10_000) // 指数退避，封顶 10s
    retries += 1
    timer = setTimeout(open, delay)
  }

  open()

  return {
    close() {
      closedByUs = true
      if (timer) clearTimeout(timer)
      ws?.close()
    },
  }
}
