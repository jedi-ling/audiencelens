// owner: agent-1（见 zh/enum.ethics_severity.ts 的文件头）
// 三档都带上 "risk"：它们标注的是**违规项**，光写 High / Medium / Low
// 在英文里会被读成"重要程度"，而这里说的是危害程度。
import type { Messages } from '@/i18n/types'

export default {
  high: 'High risk',
  medium: 'Medium risk',
  low: 'Low risk',
} satisfies Messages
