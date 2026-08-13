// 移动端抽屉菜单的无障碍标签。owner: batch-0。
// aria-label / title / placeholder 全部进 key 表（契约 6.9）——
// 英文界面上留一个中文 aria-label，屏幕阅读器会用英文语音去念中文，念不出来。
import type { Messages } from '@/i18n/types'

export default {
  toggle_aria: '菜单',
  drawer_aria: '导航菜单',
} satisfies Messages
