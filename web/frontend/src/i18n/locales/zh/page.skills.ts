/**
 * 技能中心（SkillSelectPage）。
 *
 * owner: 集成验收 agent —— 契约 4.3 把这一页划给了 agent 11（`page.skills.ts`），
 * 但 batch-1 的 12 个分片里**没有人认领它**，整页在集成时仍是硬编码中文。
 * 这份语料是补做的，key 形状与其余 page.* 一致，后续维护仍按契约走。
 *
 * 页面上还有三类中文**不在这里**，它们各有别的 owner：
 *   · skill.name / skill.description —— 后端 /api/skills 是唯一事实源（D5），
 *     英文走后端 catalog.en-US.json 的 `skill.<type>.name`；前端离线兜底那份由
 *     `npm run i18n:sync-catalog` 生成，**不许手写**。
 *   · TASK_TYPES[].name（任务类型标签）—— 同上，走 catalog.task_type overlay。
 *   · deco.use_cases（典型用例词条）—— 住在 lib/skills.ts 的展示装饰里，属 batch-0。
 * 三者都还没交付，所以英文界面上这三处仍会显示中文，已记进交付报告。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '技能中心',

  'header.title': '技能中心',
  // 原文对 4 个技能一视同仁地说"提供差异化的评审策略和角色配置"，
  // 但实际只有红队对抗与受众面板会往提示词里加视角说明。tsx 里那段注释记录了
  // 为什么改成只承诺"换一种视角"——译文必须跟着这个更弱、也更真的说法走。
  'header.subtitle':
    '选择评审技能：技能决定评审员以哪种视角来看你的材料，具体人数和角色仍由你在创建评审时选择',

  // 加载失败。这一页刻意区分"后端说一个技能都没有"和"根本没加载上"：
  // 后者必须让用户看见，否则会被当成"我的技能被停用了"。
  'list_error.title': '技能列表没能加载出来',
  'list_error.desc': '{{reason}}——这不代表你的技能被停用了，只是这次没取到列表，请重试。',
  'list_error.cta': '重新加载',

  'list.empty': '当前账号下没有可用的评审技能',

  'card_task_types.label': '可选任务类型（{{count}}）',
  'card_use_cases.label': '典型用例',
  'card.cta': '使用此技能创建评审',
  // 不能创建评审的技能，入口是真的不可点。留一个点了没用的按钮，
  // 用户的代价是一次评审额度加一份答非所问的报告。
  'card_disabled.hint':
    '该技能还没有接入评审流程：从这里创建评审不会改变评审的跑法，所以入口先关掉，等它真正可用再开放。',
} satisfies Messages
