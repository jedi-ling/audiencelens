/**
 * PersonaRadarChart 的图例默认系列名。owner: agent-10。
 * 落在 common.* 的理由与 common.persona_card.ts 相同（域是闭集）。
 *
 * 这两条只在调用方没传 name1 / name2 时才出现（对比模式下 PersonasPage 会传真名）。
 * 它们是**默认参数**，必须在每次调用时求值——存成模块级常量会让切语言后图例
 * 一直停在打开页面时的那种语言，见 PersonaRadarChart 的注释。
 */
import type { Messages } from '@/i18n/types'

export default {
  'series_a.label': '角色 A',
  'series_b.label': '角色 B',
} satisfies Messages
