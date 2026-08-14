// owner: agent-10。见 zh/enum.persona_status.ts。
// 英文侧与 page.history 的 state 块**刻意措辞不同**：那边说的是一次评审在队列里的
// 状态（Queued），这边说的是面板里某个人格轮到没轮到（Waiting）。
import type { Messages } from '@/i18n/types'

export default {
  pending: 'Waiting',
  running: 'Reviewing',
  completed: 'Done',
  failed: 'Failed',
} satisfies Messages
