/**
 * executive_summary.evidence_quality 的四档。owner: agent-1（ReportPage）。
 *
 * 这一档说的是"报告结论背后的证据够不够"，不是"材料质量"，
 * 译文里不要出现"材料"两个字，否则用户会以为在评价自己上传的东西。
 */
import type { Messages } from '@/i18n/types'

export default {
  strong: '充分',
  medium: '中等',
  weak: '偏弱',
  insufficient: '不足',
} satisfies Messages
