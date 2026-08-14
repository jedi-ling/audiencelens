// owner: batch-0。见 zh/error.ws.ts 的文件头。
import type { Messages } from '@/i18n/types'

export default {
  unavailable: 'Live updates are unavailable — falling back to periodic refresh',
  // 带 count 的 key 在 en 侧必须同时有 _one / _other（i18n:check 卡这条）。
  // 这里两条措辞一致是刻意的：序数在英文里不受复数影响，
  // 但 key 表结构必须完整，否则第 3 次重连会落到裸 key 上。
  reconnecting_one: 'Connection lost — reconnecting (attempt {{count}})',
  reconnecting_other: 'Connection lost — reconnecting (attempt {{count}})',
  give_up: 'Could not reconnect — please reload the page',
  closed: 'Live updates closed',
  // ⚠ {{message}} 本期仍是后端推来的中文原文（str(exc)），英文界面上会混中文。
  // 我们知道，且刻意不加兜底遮住它。见 zh 侧同一条的注释。
  review_failed: 'Review failed: {{message}}',
} satisfies Messages
