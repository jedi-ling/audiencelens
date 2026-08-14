/**
 * executive_summary.release_risk 的四个档位。owner: agent-1（ReportPage）。
 *
 * 契约 §3.4 例 7：**只有 label 进这张表**，color / bg / border 留在 tsx——
 * 样式不是文案，跟着译文走会让"改配色"和"改译文"变成同一个 diff。
 *
 * 叶子 = 后端枚举值原样，不做大小写转换。
 * 取值不在这四档里（或 executive_summary 根本没给）时**不在这里兜底**：
 * ReportPage 会显示「—」并另起一句说明缺了什么（page.report.summary_risk_*.desc）。
 * 兜底成「中风险」是被修掉过的老 bug——用户会拿一个编造的等级做发布决策。
 */
import type { Messages } from '@/i18n/types'

export default {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '极高风险',
} satisfies Messages
