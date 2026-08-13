/**
 * 人格的总体立场（PersonaCard 的 primaryStance）。owner: agent-10。
 *
 * 叶子 = mock-data.ts 的 PrimaryStance 取值（advocate / neutral / skeptic / blocker）。
 *
 * ⚠ **不要**把这张表和 TASK_TYPES[].stance_enum 混为一谈。
 * 那一组（「值得推进」「不值得」「观望」…）是**引擎的聚类键**、后端 parity 测试
 * 逐字保护、永不翻译，它的英文显示标签由后端 stance_labels_en 下发（契约 D4）。
 * 这里这四个是前端自己的四档归一化立场，是纯显示层，可以翻。
 *
 * 文件名用 primary_stance 而不是 stance，就是为了让这条区别在文件名上就看得见。
 */
import type { Messages } from '@/i18n/types'

export default {
  advocate: '支持',
  neutral: '中立',
  skeptic: '质疑',
  blocker: '反对',
} satisfies Messages
