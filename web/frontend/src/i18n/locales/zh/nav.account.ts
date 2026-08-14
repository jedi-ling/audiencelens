// 顶栏账户区（下拉菜单 / 游客入口 / 登录入口）。owner: batch-0。
import type { Messages } from '@/i18n/types'

export default {
  menu_aria: '账户菜单',
  settings: '设置',
  logout: '退出登录',
  /** 未登录也有游客身份（CDK 兑换 / 匿名对话都在用），这是它的显式入口。 */
  guest: '游客',
  login: '登录',
} satisfies Messages
