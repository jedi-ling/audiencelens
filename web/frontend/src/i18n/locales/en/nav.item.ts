// owner: batch-0（见 zh/nav.item.ts 的分工提示）
import type { Messages } from '@/i18n/types'

export default {
  home: 'Home',
  ask: 'Chat review',
  history: 'History',
  // 判断复利 = 把每次评审里的判断留档、事后回填结果、算命中率。
  // 直译 "judgment compounding" 在英文里读不通，用产品实际做的事来命名。
  // ⚠ 待复核：这条译名会同时出现在导航、页面标题和教程里，定了就别再各处改。
  ledger: 'Track record',
  tutorial: 'Guide',
  skills: 'Skills',
  task_types: 'Task types',
  personas: 'Personas',
  plans: 'Pricing',
  settings: 'Settings',
  create_review: 'New review',
} satisfies Messages
