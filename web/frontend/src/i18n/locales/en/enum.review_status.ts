// owner: 集成验收 agent（见 zh/enum.review_status.ts 的文件头，含"为什么集成期才建"）
import type { Messages } from '@/i18n/types'

export default {
  // Queued 而不是 Waiting：这是"排在队里还没轮到"，不是"等某个人做点什么"。
  // 人格状态那份刻意用 Waiting，两处读起来就分得开（见 enum.persona_status.ts）。
  pending: 'Queued',
  running: 'Running',
  completed: 'Done',
  failed: 'Failed',
  cancelled: 'Cancelled',
} satisfies Messages
