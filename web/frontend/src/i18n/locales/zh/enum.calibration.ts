/**
 * 校准指标名（src/runner/calibration.py 的三项）。owner: agent-1（ReportPage）。
 *
 * 叶子 = report_json.calibration 里的字段名。
 * hallucination 这一项界面上显示的是**取反后的值**（1 - 平均幻觉率），
 * 所以标签写"无幻觉率"而不是"幻觉率"——照字段名直译会让高分读成坏消息。
 */
import type { Messages } from '@/i18n/types'

export default {
  role_consistency: '角色一致性',
  coverage: '视角覆盖度',
  hallucination: '无幻觉率',
} satisfies Messages
