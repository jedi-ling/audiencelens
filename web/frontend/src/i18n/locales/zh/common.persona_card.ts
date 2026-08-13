/**
 * PersonaCard 自身的框架文案。owner: agent-10。
 *
 * 为什么落在 common.* 而不是一个 component.* 域：
 * 域是**闭集**（common | nav | page | enum | catalog | error，见契约 3.1 与
 * scripts/i18n-gen.mjs 的 DOMAINS）。PersonaCard 是跨页复用的共享组件，
 * 它的文案既不属于某一个 page，也不是枚举，落在 common 下、以组件名做单元段
 * 是闭集里唯一说得通的位置。文件名 = key 的前两段，所以单元段一人一个组件，
 * 不会与 batch-0 的 common.ui / common.action 撞车。
 *
 * 卡片里的状态与立场标签不在这里，它们是后端枚举，在 enum.persona_status /
 * enum.primary_stance（契约 §11 判断树第 3 条）。
 */
import type { Messages } from '@/i18n/types'

export default {
  // {{value}} 已经是 formatPercent() 的产物（含 % 号），这里不要再补一个 %——
  // 百分号的位置和写法各语种不同，那是 Intl 的事。
  'confidence.value': '置信度 {{value}}',
} satisfies Messages
