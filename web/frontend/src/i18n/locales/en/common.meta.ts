// owner: batch-0
import type { Messages } from '@/i18n/types'

export default {
  // 品牌名 2026-09 起分语言：中文界面显示"千见"（见 zh 侧同一 key 的注释），
  // 英文界面/域名保持 AudienceLens——这两条不是一句话的两种翻译，故意不同形。
  title_template: '{{page}} · AudienceLens',
  description:
    'A multi-agent synthetic audience review system: a panel of personas with real preferences reviews your game concept, demo, or store page and reports where they agree and where they split.',
} satisfies Messages
