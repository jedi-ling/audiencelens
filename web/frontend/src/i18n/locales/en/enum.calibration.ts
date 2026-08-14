// owner: agent-1（见 zh/enum.calibration.ts 的文件头）
import type { Messages } from '@/i18n/types'

export default {
  role_consistency: 'Role consistency',
  coverage: 'Perspective coverage',
  // 与 zh 同理：显示值是 1 - 平均幻觉率，标签必须让"高 = 好"读得通。
  hallucination: 'Hallucination-free rate',
} satisfies Messages
