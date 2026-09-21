// 顶栏账户区（下拉菜单 / 游客入口 / 登录入口）。owner: batch-0。
import type { Messages } from '@/i18n/types'

export default {
  menu_aria: '账户菜单',
  settings: '设置',
  logout: '退出登录',
  /** 未登录也有游客身份（CDK 兑换 / 匿名对话都在用），这是它的显式入口。 */
  guest: '游客',
  login: '登录',
  /* 登录方式徽标（下拉菜单里贴在昵称旁）。QQ 登录的账号邮箱是合成占位，
     直接显示邮箱等于给用户看一串没有意义的乱码，昵称旁标个来源比给邮箱更有用。 */
  'provider_qq.badge': 'QQ 登录',
  'provider_email.badge': '邮箱登录',
} satisfies Messages
