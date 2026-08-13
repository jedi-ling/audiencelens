/**
 * 人格伦理报告里的刻板印象风险档位。owner: agent-1（ReportPage / EvaluationPage 共用）。
 *
 * 后端给的是 low/medium/high 三个字符串，**没有百分比**——报告页曾经把它当
 * 0–1 小数乘 100 显示，于是永远是 NaN% + 恒红「高风险」。三档就是三档。
 *
 * unknown 不是后端枚举值，是 stereotype_risk 读不出来（null）时的显式档位：
 * 「没测出来」和「低风险」是两回事，不许合并成一档。
 */
import type { Messages } from '@/i18n/types'

export default {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  unknown: '未知',
} satisfies Messages
