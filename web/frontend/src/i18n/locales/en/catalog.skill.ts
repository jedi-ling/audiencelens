/**
 * 【生成物 · 禁止手改】技能的展示名与描述（en）。
 *
 * 由 scripts/i18n-sync-catalog.mjs 从下面这个事实源生成：
 *   web/backend/app/i18n/catalog.en-US.json 的 skills
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
  "synthetic_playtest.label": "Synthetic playtest",
  "synthetic_playtest.desc": "Put your work in front of a persona panel that stands in for your target audience",
  "audience_panel.label": "Audience panel",
  "audience_panel.desc": "An audience panel for work outside games, for general product reviews",
  "red_team_audience.label": "Red team audience",
  "red_team_audience.desc": "Adversarial personas that go looking for weak points and risks",
  "persona_generate.label": "Persona generator",
  "persona_generate.desc": "Generate persona definitions from a domain, an audience, and your goals",
} satisfies Messages
