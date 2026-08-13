// owner: agent-1（见 zh/enum.rebuttal_status.ts 的文件头）
import type { Messages } from '@/i18n/types'

export default {
  ok: 'Both sides rebutted',
  partial: 'One side only',
  failed: 'Rebuttal did not finish',
  skipped: 'No rebuttal',
} satisfies Messages
