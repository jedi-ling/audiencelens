/**
 * 实时进度通道（WebSocket）的失败态文案。owner: batch-0。
 *
 * 后端在 WS 上**不生成任何文案**（契约 D14）：进度事件只有稳定的 event 名 +
 * 结构化 data，文案全在前端出。这样用户在进度页切语言，下一条进度立刻跟着变——
 * 进度是"此刻的界面状态"而不是产出物，这是正确行为。
 *
 * 注意与页面自己的连接提示分开：AskPage / ReviewProgressPage 的三条连接状态
 * 提示各自抽在 page.ask.* / page.progress.*，两页的语气差异是刻意的（D10）。
 * 这里放的是**语气中立、任何页面都能原样用**的那五条。
 */
import type { Messages } from '@/i18n/types'

export default {
  /** 握手失败 / 服务端没开 WS。已自动退回轮询，功能不受影响，所以措辞不吓人。 */
  unavailable: '实时通道不可用，已切换为定时刷新',
  /** 连上过又断了，且还会重试。 */
  reconnecting: '连接断开，正在重连（第 {{count}} 次）',
  /** 重试次数用尽。这时候必须给用户一个动作，否则页面就停在那里不动了。 */
  give_up: '重连失败，请刷新页面',
  /** 正常收尾后通道关闭，不是错误。 */
  closed: '实时通道已关闭',
  /**
   * review.failed 事件。{{message}} 来自后端。
   *
   * ⚠ 本期后端推的是 str(exc)，即引擎/服务层的**中文原文**，前端翻不了。
   * 契约 D14 的 P1 改动是把它换成 {code, message, message_lang}；
   * 在那之前，英文界面上这一句会混进中文，且我们知道会——记在交付报告里，
   * 不要在这里加一个"看起来处理了"的兜底把它盖住。
   */
  review_failed: '评审失败：{{message}}',
} satisfies Messages
