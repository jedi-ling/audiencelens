/**
 * 顶部导航与移动端抽屉的导航项。owner: 见下。
 *
 * ⚠ 分工提示：契约 4.3 把 Layout.tsx 与 nav.* 划给 agent 12，但 batch-0 为了
 * 给后续 12 个 agent 一个"确切可抄的样板"，已经把 Layout.tsx 整个外化完了。
 * agent 12 请**跳过 Layout.tsx 与 nav.***，只做那 5 个认证页。
 *
 * 叶子用**路由语义名**，不用序号（禁止 nav.item.item1）。
 * 改文案不动 key，改路由才动 key。
 */
import type { Messages } from '@/i18n/types'

export default {
  home: '首页',
  ask: '对话评审',
  history: '评审历史',
  // 2026-08 从「判断复利」改名：那是价值主张的词，说的是"为什么"；导航项
  // 该用动作的词，说的是"进去做什么"。ARTi 同位置叫「预测复盘」，实测更好懂。
  ledger: '预测复盘',
  tutorial: '使用教程',
  skills: '技能中心',
  task_types: '任务类型',
  personas: '角色',
  plans: '定价',
  settings: '设置',
  /** 顶栏那颗主按钮。它不在 navItems 数组里，但语义上属于导航。 */
  create_review: '新建评审',
} satisfies Messages
