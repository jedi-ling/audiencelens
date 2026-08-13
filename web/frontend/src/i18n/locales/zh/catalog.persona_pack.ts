/**
 * 人格包展示名。
 *
 * ⚠ 分工提示：契约 4.3 把 catalog.* 划给 batch-0，但 batch-0 交付时没有建这个文件，
 * 而它的唯一消费者 store/persona-store.ts 归 agent-11。契约 D5 的表里
 * **PACK_NAME_MAP 的 zh 与 en 事实源都写着"前端"**（不是"后端 catalog.en-US.json"，
 * 那一行说的是 packs 端点本身的 name 字段），所以这份译文不是离线兜底、是唯一事实源，
 * 也就不能等 i18n:sync-catalog 生成。由 agent-11 建，集成时请确认没有第二份同名文件。
 *
 * 叶子 = 后端 pack.panel_id，连字符换成下划线（段名一律 snake_case，契约 3.1）。
 * 后端加了新包而这里没跟上时，persona-store 会显示 ⟦missing:…⟧ 而不是回落成
 * 后端的中文名——英文界面上混中文且没人发现，正是契约 D8 点名禁止的形态。
 */
import type { Messages } from '@/i18n/types'

export default {
  game_core: '核心玩家',
  accessibility: '无障碍倡导',
  mobile_f2p: '移动免费',
  vr_immersive: 'VR沉浸',
  competitive_esport: '竞技选手',
  educational_serious: '教育严肃',
  family_casual: '休闲家庭',
  indie_creative: '独立创意',
  general_consumer: '通用消费者',
  startup_panel: '创业评审团',
} satisfies Messages
