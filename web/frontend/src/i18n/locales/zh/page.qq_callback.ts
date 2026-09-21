/**
 * QQ 登录回调落地页（/auth/qq）。owner: 与 page.login 同一人。
 *
 * 这一页没有可交互内容，只有三种状态：兑换中 / 失败 / 成功（成功直接跳走，
 * 不需要文案）。失败文案要说清"怎么办"，而不只是"出错了"。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'QQ 登录',
  'pending.label': '正在完成 QQ 登录…',
  'failed.title': 'QQ 登录没能完成',
  // 后端的 message 会经 tApiError 带过来；这条是后端什么都没说时的兜底。
  'failed.error': '登录过程中断了，请回到登录页重试。',
  'missing.error': '这个页面缺少登录交接码——请从登录页重新发起 QQ 登录，不要直接打开本页。',
  'retry.cta': '回到登录页',
} satisfies Messages
