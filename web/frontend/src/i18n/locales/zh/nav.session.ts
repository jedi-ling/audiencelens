// 登录过期提示条。owner: batch-0。
// 过期 token 之前会静默退回匿名——用户只会莫名其妙发现自己"没登录了"。
// 这三条的存在就是为了让那件事被说出来，翻译时别把"已过期"含糊成"请登录"。
import type { Messages } from '@/i18n/types'

export default {
  expired: '登录已过期，请重新登录',
  cta: '去登录',
  dismiss_aria: '关闭提示',
} satisfies Messages
