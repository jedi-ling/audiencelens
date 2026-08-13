// owner: agent-1（见 zh/enum.release_risk.ts 的文件头）
import type { Messages } from '@/i18n/types'

export default {
  low: 'Low risk',
  medium: 'Medium risk',
  high: 'High risk',
  // 刻意不用 "Extreme"：站内最高一档在英文语境里通行的说法是 critical，
  // 而且它与 severity 的最高档同词，两处读起来是同一把尺子。
  critical: 'Critical risk',
} satisfies Messages
