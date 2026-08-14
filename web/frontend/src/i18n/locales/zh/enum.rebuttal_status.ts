/**
 * 单个争议点的反驳完成度。owner: agent-1（ReportPage）。
 *
 * zh 文案与 src/lib/mock-data.ts 的 REBUTTAL_STATUS_LABELS 逐字一致。
 * 'ok' 之外的三档都必须让人一眼看出"这条没跑完"，不能写得像一种正常结果——
 * 徽标配色（REBUTTAL_STATUS_CLASSES）留在 mock-data，不进这张表。
 */
import type { Messages } from '@/i18n/types'

export default {
  ok: '双方均已反驳',
  partial: '仅单方反驳',
  failed: '反驳未完成',
  skipped: '未进行反驳',
} satisfies Messages
