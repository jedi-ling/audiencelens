/**
 * 「绑定邮箱」提示条——游客账号在报告页看到的常驻横幅。
 *
 * 设计边界（对应 https://…的产品讨论：赠 3 次体验评审，看完整报告时软提醒
 * 绑邮箱，否则信息会丢失）：
 * 1. **不是登录墙。** 报告内容照常渲染在这条提示条下面，不阻断任何阅读——
 *    游客已经用掉一次宝贵的体验额度，把结果扣着不给看是最差的产品决策。
 * 2. **紧迫感必须是真的。** 游客账号的邮箱是合成的、密码是随机不可登录的，
 *    整条身份链只挂在浏览器本地的一个 token 上——清缓存/换设备/换浏览器
 *    这份报告真的会永久丢失。文案只说这个真实风险，不编造"限时"之类的话术。
 *    **例外：QQ 账号。** 后端把 QQ 开的号也标成 is_guest=true，但"丢了就没了"
 *    对他不成立（随时能再用 QQ 登回来）。对他说一句一验就穿帮的狠话，会让
 *    整条提示以后都不被当真，所以 QQ 分支换成对他真实成立的好处，见下面 isQq。
 * 3. **原地转正，不重新登录。** 绑定成功后 user_id 不变，历史评审/额度
 *    全部留在原地——这也是为什么按钮文案是"绑定"不是"注册"。
 */
import { useState } from 'react'
import { Mail, Loader2, CheckCircle2 } from 'lucide-react'
import { api, setToken, claimPendingReviews } from '@/lib/apiClient'
import { useSessionStore } from '@/store/session-store'
import { tApiError } from '@/i18n/api-error'
import { t } from '@/i18n/runtime'

/** className：外边距交给调用方。报告页是常驻横幅（mb-6），设置页是账户卡片里
 *  的一个板块（mt-3），两处的间距不一样，但**绑定流程只能有一份实现**——
 *  在设置页另抄一个表单就会出现"两处校验规则不一致 / 改一处忘另一处"。 */
export default function BindEmailBanner({ className = 'mb-6' }: { className?: string } = {}) {
  const identity = useSessionStore((s) => s.identity)
  const bootstrap = useSessionStore((s) => s.bootstrap)

  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  // 只对游客账号显示；非游客（含匿名共享桶——那种连"绑"都无从谈起，
  // 得先发起一次评审才会被铸造成游客）一律不渲染。
  if (!identity?.is_guest && !done) return null

  // QQ 账号在后端也被标成 is_guest=true（它确实没密码、没真邮箱），但上面
  // 那套"只存在这个浏览器里 / 永久找不回来"的措辞对他是**假的**——他随时能
  // 再用 QQ 登回来。对用户说一句他一验就知道不成立的狠话，比不说更糟：
  // 这条提示以后就再也不会被当真。所以这里换成对 QQ 用户真实成立的好处
  // （不依赖 QQ 也能登、能收验证/找回邮件），绑定动作本身完全一样。
  const isQq = identity?.login_provider === 'qq'
  const titleKey = isQq ? 'page.report.bind_email_qq.title' : 'page.report.bind_email.title'
  const descKey = isQq ? 'page.report.bind_email_qq.desc' : 'page.report.bind_email.desc'

  if (done) {
    return (
      <div className={`${className} flex items-center gap-2 rounded-xl border border-brand-primary/30 bg-brand-primary/5 px-4 py-3 text-sm text-brand-primary`}>
        <CheckCircle2 className="h-4 w-4 shrink-0" strokeWidth={1.75} />
        {t('page.report.bind_email.success')}
      </div>
    )
  }

  const submit = async () => {
    if (!email.trim() || password.length < 8 || busy) return
    setBusy(true)
    setError(null)
    try {
      const result = await api.bindEmail(email.trim(), password)
      setToken(result.token)
      // 转正前用游客身份创建的评审都已经挂在同一个 user_id 下，理论上不需要
      // 认领；这里仍然调用一次是为了和「首次匿名发起评审」「CDK 兑换」两条
      // 铸造身份的路径保持完全一致的收尾动作，不为这一条单开例外。
      await claimPendingReviews().catch(() => {})
      await bootstrap()
      setDone(true)
    } catch (e) {
      setError(tApiError(e, 'page.report.bind_email.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`${className} rounded-xl border border-warm-orange/30 bg-warm-orange/5 p-4 md:p-5`}>
      <div className="flex items-start gap-2.5">
        <Mail className="mt-0.5 h-4 w-4 shrink-0 text-warm-orange" strokeWidth={1.5} />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-text-primary">{t(titleKey)}</p>
          <p className="mt-1 text-xs leading-relaxed text-text-secondary">{t(descKey)}</p>

          {!open ? (
            <button
              onClick={() => setOpen(true)}
              className="mt-3 rounded-md bg-warm-orange px-3 py-1.5 text-xs font-medium text-bg-primary transition-opacity hover:opacity-90"
            >
              {t('page.report.bind_email.cta')}
            </button>
          ) : (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t('page.report.bind_email_email.placeholder')}
                className="min-w-0 flex-1 rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-warm-orange/50"
              />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t('page.report.bind_email_password.placeholder')}
                className="min-w-0 flex-1 rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder-text-muted outline-none focus:border-warm-orange/50"
              />
              <button
                onClick={() => void submit()}
                disabled={busy || !email.trim() || password.length < 8}
                className="flex shrink-0 items-center gap-1.5 rounded-md bg-warm-orange px-3 py-2 text-xs font-medium text-bg-primary transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />}
                {t('page.report.bind_email_submit.cta')}
              </button>
            </div>
          )}
          {error && <p className="mt-2 text-xs text-severity-critical">{error}</p>}
        </div>
      </div>
    </div>
  )
}
