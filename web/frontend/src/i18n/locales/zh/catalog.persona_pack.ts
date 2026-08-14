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
  // 后端 src/personas/launch-compliance.yaml 与 app/i18n/catalog.en-US.json 里一直有这个包，
  // 前端漏了它。表现是角色库左下角那一栏直接漏出 ⟦missing:en:catalog.persona_pack.launch_compliance⟧
  // ——persona-store 的 packName() 查不到就显式标记，没有回落成后端中文名，所以这次是被看见的。
  // 名字取自该包 description 的第一句"上线杀手专项人格包"，与其余各条一样是短称，不是 YAML 的 name 全称。
  launch_compliance: '上线杀手',

  // ---- 人格包分类（PACK_CATEGORIES[].name）----
  // 与包名同属目录数据、同一个事实源层级，所以放同一个文件，用 category_ 前缀与包 id 区分开
  // （包 id 里不会出现 category_ 开头的值）。不另起 catalog.pack_category.ts 是因为
  // 文件名即 owner（契约 4.1），再开一个文件只是把同一批目录文案拆给两个 owner。
  // 消费方是 i18n/catalog.ts 的 getPackCategoryName()，PersonasPage 的侧栏与抽屉都走它。
  // （batch-2 接线前这四条没有消费方，PersonasPage 直接渲染 PACK_CATEGORIES[].name 的
  //   中文字面量，英文界面上这一栏是中文——那正是这四条当初被写出来要修的东西。）
  // 值必须与 mock-data.ts 的 PACK_CATEGORIES[].name 逐字相同：getPackCategoryName 带一条
  // DEV 期比对断言，改了一边没改另一边会当场抛错。
  category_player_type: '玩家类型',
  category_platform: '平台特性',
  category_special: '特殊用途',
  category_general: '通用用户',
} satisfies Messages
