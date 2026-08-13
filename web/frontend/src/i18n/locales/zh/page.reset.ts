/**
 * 用邮件链接设置新密码。owner: agent-11。
 *
 * 三种互斥形态各一个块：no_token（链接缺令牌，这一页什么也做不了）/
 * 表单本体 / done（重置成功）。合并成一句可插值的文案会让"现在到底能不能操作"
 * 这个信息被稀释掉。
 *
 * 两条校验提示（长度、两次不一致）走 common.validate.*（契约 D11），不在这里。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '设置新密码',

  'header.title': '设置新密码',

  'no_token.error': '链接不完整，缺少重置令牌。',
  'no_token.link': '重新申请重置链接',

  // {{min}} 由页面传 PASSWORD_MIN 进来，理由见 zh/page.register.ts 同名条目。
  'password.label': '新密码（至少 {{min}} 位）',
  // 见 zh/page.login.ts：遮点占位符两侧同形。
  'password.placeholder': '········',
  'confirm.label': '再输一次',
  'confirm.placeholder': '········',

  'submit.cta': '重置密码',
  'submit.error': '重置失败',

  'done.success': '密码已重置。',
  // 成功后**不自动登录**，所以这句必须有：用户得知道下一步要自己登一次。
  'done.hint': '请用新密码登录。',
  'done.cta': '去登录',
} satisfies Messages
