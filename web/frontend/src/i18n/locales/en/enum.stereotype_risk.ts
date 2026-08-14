// owner: agent-1（见 zh/enum.stereotype_risk.ts 的文件头）
import type { Messages } from '@/i18n/types'

export default {
  low: 'Low risk',
  medium: 'Medium risk',
  high: 'High risk',
  // 「没测出来」而不是「没有风险」——这条 key 存在的全部理由就是把两者分开。
  unknown: 'Not measured',
} satisfies Messages
