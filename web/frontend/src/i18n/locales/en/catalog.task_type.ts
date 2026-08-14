/**
 * 【生成物 · 禁止手改】任务类型的展示名与一句话描述（en）。
 *
 * 由 scripts/i18n-sync-catalog.mjs 从下面这个事实源生成：
 *   web/backend/app/i18n/catalog.en-US.json 的 task_types
 * 改文案要改的是那个事实源，然后跑 `npm run i18n:sync-catalog` 重新生成并提交。
 * 手改这里 → `npm run i18n:check` 会红（它逐字节比对生成结果）。
 *
 * 手写禁令的出处是契约 D5：「手写必然漂移，而漂移的表现是"同一个任务类型在两个页面
 * 显示两个英文名"」。这份 overlay 的定位是**离线兜底**，不是事实源。
 *
 * stance_enum / score_dimensions 不在这里：前者是 wire contract（永不翻译，英文标签由后端 stance_labels_en 下发），后者是后端维度 id，本来就不是文案。
 */
import type { Messages } from '@/i18n/types'

export default {
  "concept_review.label": "Concept review",
  "concept_review.desc": "Core loop, differentiation, and feasibility",
  "demo_first_play.label": "Demo first play",
  "demo_first_play.desc": "Onboarding friction, game feel, and the first 15 minutes",
  "devlog_review.label": "Devlog review",
  "devlog_review.desc": "Narrative pacing, transparency, and community response",
  "update_announcement_review.label": "Update announcement",
  "update_announcement_review.desc": "Patch notes, trust reinforcement, and retention signals",
  "monetization_review.label": "Monetization review",
  "monetization_review.desc": "Pricing, where the paywall sits, and perceived value",
  "steam_page_review.label": "Steam page review",
  "steam_page_review.desc": "Store page structure, visual pitch, and trust signals",
  "kickstarter_review.label": "Crowdfunding page review",
  "kickstarter_review.desc": "Campaign narrative, reward tiers, and building trust",
  "localization_review.label": "Localization review",
  "localization_review.desc": "Cultural fit, language quality, and UI adaptation",
  "discord_community_review.label": "Community ops review",
  "discord_community_review.desc": "Community vibe, engagement design, and member retention",
  "looking_for_party_post.label": "Looking-for-group post",
  "looking_for_party_post.desc": "Community copy, reach, and social pull",
  "product_feedback_review.label": "Product feedback review",
  "product_feedback_review.desc": "Collecting and reading general product feedback, games or not",
  "pricing_page_review.label": "Pricing page review",
  "pricing_page_review.desc": "Plan tiers, value communication, and trust signals, games or not",
  "onboarding_review.label": "Onboarding review",
  "onboarding_review.desc": "First-run experience and getting-started friction, games or not",
  "pitch_review.label": "Startup pitch review",
  "pitch_review.desc": "Decks, pitch sessions, and application forms, read by investors and diligence",
} satisfies Messages
