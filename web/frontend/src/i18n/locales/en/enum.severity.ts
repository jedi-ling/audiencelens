// owner: agent-10。见 zh/enum.severity.ts（四档，刻意不与 ethics_severity 合并）。
// 中文侧是单字（严重/高/中/低），英文没有同样紧凑的写法，用完整词——
// 徽章是 px-2 的小胶囊，"Critical" 会比中文宽约一倍，见交付报告里的撑破风险清单。
import type { Messages } from '@/i18n/types'

export default {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
} satisfies Messages
