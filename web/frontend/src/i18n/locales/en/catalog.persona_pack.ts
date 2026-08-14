// owner: agent-11（见 zh/catalog.persona_pack.ts 的文件头，含与 batch-0 的分工说明）。
//
// 译名口径：这些是**受众群体**的名字，不是产品功能名，所以按英文里怎么称呼这群人来写
// （"Core Gamers" 而不是 "Core Player Pack"），与人格档案里的 archetype 用词保持一路。
import type { Messages } from '@/i18n/types'

export default {
  game_core: 'Core Gamers',
  accessibility: 'Accessibility Advocates',
  mobile_f2p: 'Mobile F2P Players',
  vr_immersive: 'VR Immersion Seekers',
  competitive_esport: 'Competitive Esports Players',
  educational_serious: 'Educational & Serious Games',
  family_casual: 'Family & Casual Players',
  indie_creative: 'Indie Creatives',
  general_consumer: 'General Consumers',
  startup_panel: 'Startup Review Panel',
  // 与后端 app/i18n/catalog.en-US.json 的 persona_packs["launch-compliance"].name 逐字相同。
  // 那份是 packs 端点的英文名，这份是前端 overlay——同一个包在两处出现两个英文名，
  // 用户会以为是两个包，所以这里对齐后端而不是另起一个说法。
  launch_compliance: 'Launch Blockers',

  // ---- 人格包分类 ----
  // 同样与后端 catalog.en-US.json 的 pack_categories 逐字对齐。
  category_player_type: 'Player types',
  category_platform: 'Platform focus',
  category_special: 'Special purpose',
  category_general: 'General users',
} satisfies Messages
