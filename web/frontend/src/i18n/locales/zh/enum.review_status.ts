/**
 * 一次评审的执行状态（Review.status，后端枚举）。owner: 集成验收 agent。
 *
 * 为什么集成期才建这个文件：契约 §11 判断树第 3 条说"键是后端枚举 → 走 enum.*"，
 * 但 batch-0 没交付它。于是并行的三个分片各自绕了一遍：
 *   · ReviewProgressPage（agent 9）—— 报告里写明"应为 enum.review_status.*"后**保持硬编码中文**
 *   · ReviewHistoryPage（agent 10）—— 抽进了自己的 `page.history.state.*`
 *   · PersonaCard（agent 10）—— 另有 enum.persona_status.*
 * 前两者是同一个后端枚举的同一套标签，正是 D5「一个条目的英文文案只能有一个 owner」
 * 要防的分叉，所以在这里收口成一份，两个消费点都改读它。
 *
 * **不要与 enum.persona_status.* 合并**：值域不同（评审有第五档 cancelled，人格没有），
 * 而且一个说的是"这次评审"、一个说的是"这个人格"，英文侧刻意分开措辞
 * （评审 Queued / 人格 Waiting）。agent-10 在 enum.persona_status.ts 里记过这个判断。
 *
 * 叶子 = 后端枚举值原样，不做大小写转换。取值不在这五档里时**不在这里兜底**：
 * 消费点显示 ⟦missing:…⟧（样式可以回落，文案不许），否则后端新增状态会被
 * 伪装成"等待中"——那是一个看不出来的错。
 */
import type { Messages } from '@/i18n/types'

export default {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
} satisfies Messages
