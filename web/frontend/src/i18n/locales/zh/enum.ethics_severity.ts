/**
 * 伦理违规项的三档严重度。owner: agent-1（ReportPage / EvaluationPage 共用）。
 *
 * ⚠ **刻意不与 enum.severity 合并**（契约 D10）：
 * Severity 是四档（critical/high/medium/low → 严重/高/中/低），
 * EthicsSeverity 只有三档，而且 mock-data.ts:150-152 记着一条设计决定——
 * 徽标配色整体上移一档（high→critical、medium→high、low→medium），
 * 因为 severity-low 是青色，在站内读起来像「没问题」，用在违规上会误导。
 * 合并会抹掉这条有记录的决定，而且值域根本不同。
 *
 * zh 文案与 mock-data.ts 的 ETHICS_SEVERITY_LABELS 逐字一致；
 * 徽标类名（ETHICS_SEVERITY_BADGE_CLASSES）留在 mock-data，不进这张表。
 */
import type { Messages } from '@/i18n/types'

export default {
  high: '高危',
  medium: '中危',
  low: '低危',
} satisfies Messages
