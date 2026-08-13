// owner: agent-1（见 zh/enum.stop_reason.ts 的文件头）
import type { Messages } from '@/i18n/types'

export default {
  cost_budget_reached: 'Hit the cost cap — stopped adding personas',
  marginal_value_below_threshold: 'The next persona was worth less than the threshold — stopped',
} satisfies Messages
