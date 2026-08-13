/**
 * 忘记密码（申请重置链接）。owner: agent-11。
 *
 * sent.success 的措辞是**刻意含糊**的："如果该邮箱已注册" ——
 * 后端本来就不区分注册过与否（防邮箱枚举），译文也不许分成
 * "已发送 / 该邮箱不存在" 两句，那等于把后端刻意抹掉的信息又泄露回去。
 * 英文侧同理。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '找回密码',

  'header.title': '找回密码',
  'header.desc': '输入注册邮箱，我们会发一个重置链接给你',

  'email.label': '注册邮箱',
  'email.placeholder': 'you@example.com',

  'submit.cta': '发送重置链接',
  'submit.error': '发送失败',

  'sent.success': '如果该邮箱已注册，重置链接已经发出。',
  'sent.hint': '链接 60 分钟内有效，只能使用一次。没收到请检查垃圾邮件箱。',
  'sent.link': '返回登录',

  'signin.hint': '想起来了？<link>直接登录</link>',
} satisfies Messages
