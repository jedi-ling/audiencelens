/**
 * 单个人格在一次评审里的执行状态（PersonaCard）。owner: agent-10。
 *
 * 叶子 = mock-data.ts 的 PersonaStatus 取值。
 *
 * **刻意不与 page.history 的 state 块合并**（契约 §11 判断树第 4 条）：
 * 两者措辞逐字相同，但值域不同——评审状态有第五档 cancelled，人格状态没有；
 * 而且一个说的是"这次评审"、一个说的是"这个人格"，英文侧完全可能要分开措辞
 * （评审 Queued / 人格 Waiting）。逐字相同也各抽各的，由 batch-0 决定要不要合并。
 */
import type { Messages } from '@/i18n/types'

export default {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
} satisfies Messages
