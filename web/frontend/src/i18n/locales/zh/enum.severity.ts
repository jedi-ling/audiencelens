/**
 * 问题严重度（SeverityBadge）。owner: agent-10。
 *
 * 叶子 = 后端枚举值原样（critical / high / medium / low），不做大小写转换。
 *
 * **刻意不与 enum.ethics_severity 合并**（契约 D10 / 3.4 例 9）：
 * 这里是四档，伦理违规那边只有三档（高危/中危/低危），值域根本不同；
 * 而且 mock-data.ts:150-152 的注释记录了"三档整体上移一档"的设计决定
 * （severity-low 是青色，在站内读起来像没问题，用在违规上会误导）。
 * 合并会抹掉一个有记录的设计决定。
 */
import type { Messages } from '@/i18n/types'

export default {
  critical: '严重',
  high: '高',
  medium: '中',
  low: '低',
} satisfies Messages
