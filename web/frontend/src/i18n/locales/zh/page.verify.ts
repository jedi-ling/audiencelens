/**
 * 邮箱验证落地页（从邮件链接进来，自动消费令牌）。owner: agent-11。
 *
 * 三态各一个块：pending / ok / fail。fail 下面还分两种来源——
 * no_token（链接本身就缺令牌，一次请求都没发）与 confirm（发了、后端拒绝了）。
 * 分开是因为用户能做的事不一样：前者要重新点邮件里的链接，后者要重发一封。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '邮箱验证',

  'pending.loading': '正在验证…',

  'ok.title': '邮箱已验证',
  'ok.cta': '开始评审',

  'fail.title': '验证未成功',
  'fail.hint': '验证链接 24 小时内有效且只能用一次。可到「设置」页重新发送。',
  'fail.link': '去设置页',

  'no_token.error': '链接不完整，缺少验证令牌',
  // tApiError 的 fallbackKey：令牌被拒的具体原因由后端 message 说，
  // 这条只在拿不到 ApiError（网络断了之类）时顶上。
  'confirm.error': '验证失败',
} satisfies Messages
