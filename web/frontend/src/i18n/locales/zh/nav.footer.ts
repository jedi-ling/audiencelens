/**
 * 页脚。owner: batch-0。
 *
 * 不在这里的两样东西，是刻意的：
 *   - 版本号 v1.0.0 —— 不是文案。
 *   - ICP 备案号 —— 是法定登记号，逐字符固定，翻译或改写都是违规。
 *     它留在 Layout.tsx 里当字面量，i18n-scan 的允许清单单列了它。
 */
import type { Messages } from '@/i18n/types'

export default {
  tagline: '多代理合成用户评审系统',
  privacy: '隐私政策',
  terms: '服务条款',
  /** 备案号那条外链的无障碍说明。号码本身不翻，这句说明它是什么。 */
  icp_aria: '工信部 ICP 备案查询',
} satisfies Messages
