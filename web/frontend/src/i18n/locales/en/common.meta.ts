// owner: batch-0
import type { Messages } from '@/i18n/types'

export default {
  // 与 zh 侧字面相同，但不含中文，所以不触发 i18n:check 的"en 不许照抄 zh"断言。
  // 品牌名不翻译，分隔符两侧语言中性——这是刻意的，不是漏译。
  title_template: '{{page}} · AudienceLens',
  description:
    'A multi-agent synthetic audience review system: a panel of personas with real preferences reviews your game concept, demo, or store page and reports where they agree and where they split.',
} satisfies Messages
