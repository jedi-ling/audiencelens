/**
 * 可证伪预测里 target_metric 的变化方向。owner: agent-1（ReportPage）。
 * 只在指标名后面的括号里出现（"付费转化率（提升）"），所以是短词不是句子。
 */
import type { Messages } from '@/i18n/types'

export default {
  increase: '提升',
  decrease: '降低',
} satisfies Messages
