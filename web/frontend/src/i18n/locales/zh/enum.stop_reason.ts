/**
 * 自适应面板停止扩面的原因（adaptive_panel.decisions[].stop_reason）。
 * owner: agent-1（ReportPage）。
 */
import type { Messages } from '@/i18n/types'

export default {
  cost_budget_reached: '触发成本上限，停止扩面',
  marginal_value_below_threshold: '继续扩面的边际价值低于阈值，停止',
} satisfies Messages
