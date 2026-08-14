/**
 * 【生成物 · 禁止手改】任务类型的展示名与一句话描述（zh）。
 *
 * 由 scripts/i18n-sync-catalog.mjs 从下面这个事实源生成：
 *   src/lib/mock-data.ts 的 TASK_TYPES（源行受契约 D6 保护，一个字不改，这里只是照抄）
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
  "concept_review.label": "概念评审",
  "concept_review.desc": "核心循环、差异化、可行性",
  "demo_first_play.label": "Demo首玩",
  "demo_first_play.desc": "上手摩擦、手感、首15分钟体验",
  "devlog_review.label": "开发日志评审",
  "devlog_review.desc": "叙事节奏、透明度、社区反馈",
  "update_announcement_review.label": "更新公告",
  "update_announcement_review.desc": "版本日志、信任强化、留存信号",
  "monetization_review.label": "商业化评审",
  "monetization_review.desc": "定价、付费边界、价值感知",
  "steam_page_review.label": "Steam页评审",
  "steam_page_review.desc": "商店页信息架构、视觉传达、信任信号",
  "kickstarter_review.label": "众筹页评审",
  "kickstarter_review.desc": "众筹页叙事、回报设计、信任建立",
  "localization_review.label": "本地化评审",
  "localization_review.desc": "文化适配、语言质量、UI适配",
  "discord_community_review.label": "社区运营评审",
  "discord_community_review.desc": "社区氛围、互动设计、用户留存",
  "looking_for_party_post.label": "找搭子帖",
  "looking_for_party_post.desc": "社区文案、传播性、社交吸引力",
  "product_feedback_review.label": "产品反馈评审",
  "product_feedback_review.desc": "通用产品反馈收集与解读，不限游戏",
  "pricing_page_review.label": "定价页评审",
  "pricing_page_review.desc": "定价分层、价值传达、信任信号，不限游戏",
  "onboarding_review.label": "新手引导评审",
  "onboarding_review.desc": "首次使用体验、上手摩擦，不限游戏",
  "pitch_review.label": "创业项目评审",
  "pitch_review.desc": "BP/路演/申报表，投资人与尽调视角，不限行业",
} satisfies Messages
