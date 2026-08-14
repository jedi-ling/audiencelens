/**
 * 交叉质询的三档执行方式。owner: agent-1（ReportPage）。
 *
 * zh 侧的文案与 src/lib/mock-data.ts 的 CROSS_EXAM_MODE_LABELS /
 * CROSS_EXAM_MODE_DESCRIPTIONS **逐字一致**，那两份常量是既有事实源，
 * 这里是它们的 i18n 出口。措辞口径来自 src/runner/cross_exam.py：
 * 尤其 moderated 档必须写明"不是每个人格各自独立重新发言"——含糊就是撒谎。
 *
 * label 与 desc 分开成两条 key：label 进徽标（短），desc 进说明块（整段），
 * 两者改动频率与长度约束都不一样。
 */
import type { Messages } from '@/i18n/types'

export default {
  'derived_summary.label': '派生摘要（未进行反驳轮）',
  'moderated_rebuttal.label': '仲裁式反驳（1 轮）',
  'multi_agent_rebuttal.label': '多智能体反驳',

  'derived_summary.desc':
    '本节没有进行反驳轮：内容全部由各人格独立评审时的原始输出派生而来，人格之间没有相互反驳，也没有人因此改票。',
  'moderated_rebuttal.desc':
    '本次执行了一次仲裁式反驳轮：模型拿到双方已记录的论据后统一给出反驳与更新后的立场。这不是每个人格各自独立重新发言。',
  'multi_agent_rebuttal.desc':
    '本次执行了多智能体反驳：每位涉事人格都带着对手的论据被重新调用一次，各自产出反驳与最终立场。',
} satisfies Messages
