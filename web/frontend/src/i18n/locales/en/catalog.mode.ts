/**
 * 【生成物 · 禁止手改】评审模式的描述（en）。
 *
 * 由 scripts/i18n-sync-catalog.mjs 从下面这个事实源生成：
 *   web/backend/app/i18n/catalog.en-US.json 的 review_modes
 * 改文案要改的是那个事实源，然后跑 `npm run i18n:sync-catalog` 重新生成并提交。
 * 手改这里 → `npm run i18n:check` 会红（它逐字节比对生成结果）。
 *
 * 手写禁令的出处是契约 D5：「手写必然漂移，而漂移的表现是"同一个任务类型在两个页面
 * 显示两个英文名"」。这份 overlay 的定位是**离线兜底**，不是事实源。
 *
 * 没有 name：后端 REVIEW_MODES 压根没有 name 字段，档位名（快速 / 标准 / 完整）的 owner 是 enum.mode_badge.*，在这里再给一份就是给同一个词立第二个 owner。
 */
import type { Messages } from '@/i18n/types'

export default {
  "quick.desc": "Quick screen, results in under five minutes",
  "standard.desc": "Everyday review, balanced for speed and depth",
  "full.desc": "Formal review, the complete pipeline",
} satisfies Messages
