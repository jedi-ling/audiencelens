/**
 * 自适应面板被禁用的原因（report.adaptive_panel.disabled_reason）。
 * owner: agent-1（ReportPage）。
 *
 * "请求了但没启用"必须说清楚为什么，不能装作用户没请求过——
 * 这是 AdaptivePanelSection 把 requested 与 enabled 分开展示的全部理由。
 */
import type { Messages } from '@/i18n/types'

export default {
  explicit_persona_selection:
    '你显式点名了角色，少跑其中任何一个都会违背你的意图，因此本次保持固定面板',
} satisfies Messages
