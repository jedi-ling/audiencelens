/**
 * 评审模式徽标（ReviewMode: quick / standard / full）。owner: agent-1（ReportPage）。
 *
 * 只有档位名进这里，"…模式"那半句在 page.report.header.badge——
 * 中文是后缀、英文是后缀在词序上的位置不同，拼在一起会锁死英文语序。
 * 徽标的配色与图标留在 tsx（契约 §3.4 例 7）。
 */
import type { Messages } from '@/i18n/types'

export default {
  quick: '快速',
  standard: '标准',
  full: '完整',
} satisfies Messages
