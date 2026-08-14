/**
 * 注册页。owner: agent-11。
 *
 * 密码长度提示走 common.validate.password_min（契约 D11），这里不重写一遍——
 * 五个认证页 + 设置页 + 创建评审页的校验文案共用一份，改规则只改一处。
 *
 * terms.consent 是整句带两个链接：链接文字**必须留在消息串里**，
 * 否则英文语序改不动（契约 §3.4 例 6 / D13）。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '注册',

  'header.title': '注册',
  'header.desc': '不登录也能体验评审——注册只是为了解锁完整报告和历史记录',

  'name.label': '昵称（可选）',
  'name.placeholder': '怎么称呼你',
  'email.label': '邮箱',
  // 见 zh/page.login.ts：保留域名与遮点占位符两侧同形。
  'email.placeholder': 'you@example.com',
  // {{min}} 由页面传 PASSWORD_MIN 进来，不写死 8——写死的话改了校验规则，
  // 标签还会继续说"至少 8 位"，而那是**界面在撒谎**。
  'password.label': '密码（至少 {{min}} 位）',
  'password.placeholder': '········',

  'submit.cta': '注册',
  'submit.pending': '注册中…',
  'submit.error': '注册失败',

  'terms.consent': '注册即表示你同意<terms>服务条款</terms>与<privacy>隐私政策</privacy>',

  'signin.hint': '已经有账号？<link>直接登录</link>',
} satisfies Messages
