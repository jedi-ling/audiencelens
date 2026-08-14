/**
 * 登录页。owner: agent-11。
 *
 * 表单校验文案**不在这里**：'请输入有效的邮箱地址' / '密码至少 8 位' 这类
 * 一律走 common.validate.*（契约 D11），页面只读不写。
 * 这里只放这一页独有的措辞。
 *
 * 提交按钮的三态（可点 / 进行中 / 失败）各一条 key，不做插值——
 * 三元里的分支条件是行为逻辑，不该被 i18n 层吃掉（同 nav.verify_banner 的口径）。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '登录',

  'header.title': '登录',
  'header.desc': '登录后可以查看完整评审报告、保存你的评审历史',

  'email.label': '邮箱',
  // 示例邮箱两侧字面相同：它是 RFC 2606 保留域名，不是文案，翻不出第二种写法。
  'email.placeholder': 'you@example.com',
  'password.label': '密码',
  // 密码框的遮点占位符，两侧同形。它是视觉遮罩不是文字，翻译它没有意义。
  'password.placeholder': '········',

  'forgot.link': '忘记密码？',

  'submit.cta': '登录',
  'submit.pending': '登录中…',
  // tApiError 的 fallbackKey：非 ApiError（网络层 TypeError 之类）时用它，
  // 而不是把 "Failed to fetch" 原样甩给用户。
  'submit.error': '登录失败',

  // 整句带链接 → Trans + 具名 slot。链接文字**不拆出去**：拆了英文语序就改不动了
  //（en 侧完全可以写成 "Need an account? <link>…</link>" 之外的语序）。见契约 §3.4 例 6。
  'signup.hint': '还没有账号？<link>注册一个</link>',
} satisfies Messages
