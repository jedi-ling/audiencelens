/**
 * 角色库页。owner: agent-8（PersonasPage.tsx）。
 *
 * 这里**只有页面框架的文案**。人格本身的字段（name / archetype /
 * identity_summary / decision_rules / triggers）一律不进这张表：
 * 契约 10.3 已经裁定人格身份不做本地化——张伟在英文模式下仍叫张伟，
 * 因为 region / age_range 会被拼进报告的 recruit_types，用户会照着去招募真人。
 *
 * 角色包名（pack.name）与包分类名（PACK_CATEGORIES[].name）也不在这里：
 * 它们是目录数据，事实源与 owner 都是 batch-0（契约 D5 / 4.3），
 * 页面只负责渲染。在这里再写一份就是第二套译名。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '角色库',
  'header.title': '角色库',

  // ---- 左侧 / 抽屉里的角色包筛选 ----
  // 桌面侧栏与移动端抽屉共用同一段 sidebarContent，标题也共用一条 key：
  // 它们是同一个结构块的同一个标题，不是两处措辞碰巧相同（契约 §11 判断树）。
  'filter.title': '角色包筛选',
  filter_all: '全部',
  // 小屏顶部那颗打开抽屉的按钮
  'filter.cta': '筛选',
  'search.placeholder': '搜索角色...',
  // 角色的 pack 在 packs 列表里找不到时显示它。这不是缺译（缺译走 ⟦missing:…⟧），
  // 是**数据缺口**：后端没回这个包。所以照实说"未知"，而不是拿包 id 顶上去。
  pack_unknown: '未知',

  // ---- 对比模式 ----
  compare_enter: '对比模式',
  compare_exit: '退出对比',
  'compare.title': '角色对比',
  // 卡片上那颗把这个角色加进对比的小按钮
  'compare.label': '对比',

  // ---- 展开后的角色详情 ----
  'rules.title': '决策规则',
  'triggers.title': '触发器',

  // ---- 状态 ----
  'list.pending': '加载角色数据...',
  'list_empty.title': '没有匹配的角色',
  'list_empty.desc': '试试清除搜索词或选择「全部」',
  'list_empty.cta': '清除搜索',
} satisfies Messages
