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

  /* ---------------- QQ 登录失败回执 ----------------
     后端把每一种 QQ 登录失败（用户取消授权 / state 不匹配 / 腾讯侧报错）都
     302 回 /login?qq_error=<原因>。这一页此前根本不读这个参数，用户被甩回
     一个空白登录表单，既没有报错也没有解释——表现就是"点了 QQ 登录，什么都没发生"。
     原因串是后端的中文自由文本（不是稳定 code），所以它只能当**详情行**，
     主句必须是本地化的（契约 D2：英文界面不能只剩一句中文）。 */
  'qq_error.error': 'QQ 登录没有完成',
  'qq_error.hint': '服务端给出的原因（中文原文）：{{reason}}',

  /* ---------------- 游客提醒 ----------------
     铸造出来的游客现在**能**进这一页了（此前被无条件弹去 /ask，唯一出路是
     登出，而登出会连他的评审和剩余次数一起丢掉）。既然放他进来，就得把
     "登录别的账号 = 换一个身份"说清楚，并指出唯一能保住当前东西的做法。 */
  'guest_notice.title': '你现在是这台浏览器上的游客',
  'guest_notice.desc':
    '登录另一个账号会直接切换过去，这台浏览器上的游客评审与剩余次数不会跟着走。想保住它们，请先去<link>设置里绑定邮箱</link>把当前游客身份转成正式账号——绑定后 user_id 不变，历史与额度都留在原地。',

  /* QQ 登录入口。只在后端三项配齐（config.qq_login_enabled）时才渲染。 */
  'oauth_divider.label': '或',
  'qq.cta': '使用 QQ 登录',
} satisfies Messages
