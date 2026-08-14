/**
 * 【生成物 · 禁止手改】技能的展示名与描述（zh）。
 *
 * 由 scripts/i18n-sync-catalog.mjs 从下面这个事实源生成：
 *   src/lib/mock-data.ts 的 SKILLS（name / description_zh）
 * 改文案要改的是那个事实源，然后跑 `npm run i18n:sync-catalog` 重新生成并提交。
 * 手改这里 → `npm run i18n:check` 会红（它逐字节比对生成结果）。
 *
 * 手写禁令的出处是契约 D5：「手写必然漂移，而漂移的表现是"同一个任务类型在两个页面
 * 显示两个英文名"」。这份 overlay 的定位是**离线兜底**，不是事实源。
 *
 * ⚠ 技能页与创建评审页读的是 **后端返回的行**（lib/skills.ts 的 SkillTruth），不是这张表。这张表是"后端拉不到"时的离线兜底，且中文侧措辞与后端那份不完全一致——详见 scripts/i18n-sync-catalog.mjs 文件头最后一段。
 */
import type { Messages } from '@/i18n/types'

export default {
  "synthetic_playtest.label": "合成试玩",
  "synthetic_playtest.desc": "模拟真实玩家试玩体验，从上手到深度体验全流程评估，发现设计盲点与体验断裂",
  "audience_panel.label": "受众面板",
  "audience_panel.desc": "组建目标受众虚拟焦点小组，收集不同人群的真实反应与偏好，量化市场接受度",
  "red_team_audience.label": "红队对抗",
  "red_team_audience.desc": "用对抗性视角主动攻击产品弱点，模拟最挑剔的用户和恶意场景，暴露隐藏风险",
  "persona_generate.label": "人格生成",
  "persona_generate.desc": "定制人格生成能力（暂未接入评审流程）。从这里创建的评审走的是标准流程，不会额外生成人格。",
} satisfies Messages
