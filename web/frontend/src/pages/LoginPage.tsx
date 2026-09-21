import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { LogIn, UserRound } from 'lucide-react'
import { useSessionStore } from '@/store/session-store'
import { isMintedGuest, isRealAccount } from '@/lib/types'
import { t, Trans } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { tApiError } from '@/i18n/api-error'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useSessionStore((s) => s.login)
  const identity = useSessionStore((s) => s.identity)
  // config 可能还没拉回来（bootstrap 未完成）——那时按"没开"处理，
  // 宁可晚一拍出现按钮，也不要画一个点了必然失败的入口。
  // 走 store 的派生访问器而不是直接读 config：config 的解读收敛在一处
  // （同 canReview），后端字段改名时只有 store 需要跟着改。
  const qqEnabled = useSessionStore((s) => s.qqLoginEnabled())
  // 顺带订阅了 ui_lang（内部 useLocale），切语言时整页重新求值 t()
  useDocumentTitle('page.login.meta.title')

  const [searchParams, setSearchParams] = useSearchParams()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  /** QQ 登录失败时后端回传的**中文原文**原因。null = 本次不是 QQ 失败回来的；
   *  空串 = 失败了但后端没给原因（此时只出主句，不画一条空的详情行）。
   *  存原文而不是存 t() 的结果：t() 是普通函数，存结果的话切语言后这条提示
   *  会一直停在打开页面时的那种语言。 */
  // QQ 登录失败回执。后端把每一种失败（用户取消授权 / state 不匹配 / 腾讯侧报错）
  // 都 302 回 /login?qq_error=<原因>，而这一页此前根本不读它——用户被甩回一个
  // 空白登录表单，既没有报错也没有解释，表现就是"点了 QQ 登录，什么都没发生"。
  //
  // 首帧就从 URL 里取值（useState 的惰性初值），而不是在 effect 里 setState：
  // 后者会先渲染一帧"没有报错"的空表单再补上，既闪一下，也是 React 19
  // set-state-in-effect 规则点名的写法。下面那个 effect 只负责抹掉地址栏里的
  // 参数，不再参与决定显示什么。
  const [qqError, setQqError] = useState<string | null>(() =>
    searchParams.has('qq_error') ? (searchParams.get('qq_error') ?? '') : null
  )

  // 读完立刻把参数抹掉（replace，不往历史里多塞一条）：留着的话用户刷新或
  // 用邮箱重试失败之后，地址栏里那条**上一次**的原因还会被当成本次的贴回来。
  useEffect(() => {
    if (!searchParams.has('qq_error')) return
    const next = new URLSearchParams(searchParams)
    next.delete('qq_error')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams])

  // 已登录还停在登录页没有意义——直接送进应用。
  // 但**只弹真正的账号**：首次匿名评审现在会铸造一个游客身份，用 is_anonymous
  // 判断的话，跑过一次评审的人从此再也进不来登录页登自己的真账号，唯一出路是
  // 登出——而登出会丢掉游客 token，连他的评审和剩余次数一起丢。见 isRealAccount。
  useEffect(() => {
    if (isRealAccount(identity)) navigate('/ask', { replace: true })
  }, [identity, navigate])

  /** 走 form 的 onSubmit：回车、点按钮、密码管理器自动填充后提交，三条路径同一个出口。 */
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password || busy) return
    setBusy(true)
    setError(null)
    setQqError(null) // 这次是邮箱登录，上一次 QQ 失败的回执不该继续挂着
    try {
      await login(email.trim(), password)
      navigate('/ask') // 落进应用而不是营销落地页
    } catch (err) {
      // tApiError 而不是 err.message：后者在网络层会把 "Failed to fetch" 原样甩给用户，
      // 在英文界面上还会把后端中文原文并排显示出来。
      setError(tApiError(err, 'page.login.submit.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <LogIn className="h-6 w-6 text-brand-primary" strokeWidth={1.5} />
        <h1 className="text-xl font-semibold text-text-primary font-display">
          {t('page.login.header.title')}
        </h1>
        <p className="text-sm text-text-secondary">{t('page.login.header.desc')}</p>
      </div>

      {/* 游客提醒。既然放游客进这一页（见上面的 isRealAccount 注释），
          就得把"登录别的账号 = 换一个身份"说清楚，并指出唯一能保住
          当前评审与剩余次数的做法（绑邮箱转正，user_id 不变）。 */}
      {isMintedGuest(identity) && (
        <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-warm-orange/30 bg-warm-orange/5 p-4">
          <UserRound className="mt-0.5 h-4 w-4 shrink-0 text-warm-orange" strokeWidth={1.5} />
          <div className="min-w-0">
            <p className="text-sm font-medium text-text-primary">{t('page.login.guest_notice.title')}</p>
            <p className="mt-1 text-xs leading-relaxed text-text-secondary">
              <Trans
                k="page.login.guest_notice.desc"
                slots={{
                  link: (s) => (
                    <Link
                      to="/settings"
                      className="text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim"
                    >
                      {s}
                    </Link>
                  ),
                }}
              />
            </p>
          </div>
        </div>
      )}

      {/* 必须是真的 <form>：此前是一堆 input + 一个 onClick 的 div 式提交，
          代价不只是"不够规范"——回车提交要靠每个输入框自己挂 onKeyDown（漏一个就不灵）、
          浏览器和密码管理器认不出这是登录表单（不提示保存、自动填充后无法提交）、
          读屏软件也拿不到表单语义。 */}
      <form onSubmit={submit} className="rounded-xl border border-white/[0.08] bg-black/30 p-6">
        <label htmlFor="login-email" className="block text-xs text-text-muted">
          {t('page.login.email.label')}
        </label>
        <input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder={t('page.login.email.placeholder')}
          autoFocus
        />

        <label htmlFor="login-password" className="mt-4 block text-xs text-text-muted">
          {t('page.login.password.label')}
        </label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder={t('page.login.password.placeholder')}
        />

        <div className="mt-2 text-right">
          <Link
            to="/forgot-password"
            className="text-xs text-text-muted underline underline-offset-2 hover:text-brand-primary"
          >
            {t('page.login.forgot.link')}
          </Link>
        </div>

        {/* role=alert：登录失败是需要立刻被读屏软件念出来的，不能只是视觉上变红。
            QQ 失败回执与表单提交失败共用这个槽位：主句恒为本地化文案，后端那句
            中文原因只当**详情行**（契约 D2——英文界面上不能只剩一句中文）。 */}
        {(error || qqError !== null) && (
          <div role="alert" className="mt-3">
            <p className="text-sm text-severity-critical">
              {error ?? t('page.login.qq_error.error')}
            </p>
            {!error && qqError ? (
              <p className="mt-1 text-xs leading-relaxed text-text-muted">
                {t('page.login.qq_error.hint', { reason: qqError })}
              </p>
            ) : null}
          </div>
        )}

        <button
          type="submit"
          disabled={busy || !email.trim() || !password}
          className="mt-6 flex h-11 w-full items-center justify-center rounded-lg bg-brand-primary text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors disabled:opacity-50"
        >
          {busy ? t('page.login.submit.pending') : t('page.login.submit.cta')}
        </button>
      </form>

      {qqEnabled && (
        <>
          {/* 分隔线只在真有第三方入口时才画——没有 QQ 登录时它就是一条
              指向空白的装饰线。 */}
          <div className="mt-6 flex items-center gap-3">
            <span className="h-px flex-1 bg-border" />
            <span className="text-xs text-text-muted">{t('page.login.oauth_divider.label')}</span>
            <span className="h-px flex-1 bg-border" />
          </div>
          {/* 用整页跳转而不是 fetch：OAuth 授权必须由浏览器地址栏发起，
              XHR 拿不到腾讯的登录态、也过不了它的跨域策略。 */}
          <a
            href="/api/auth/qq/authorize"
            className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-lg border border-border bg-bg-card text-sm font-medium text-text-primary transition-colors hover:border-brand-primary/40 hover:bg-bg-card-hover"
          >
            <QQMark />
            {t('page.login.qq.cta')}
          </a>
        </>
      )}

      <p className="mt-4 text-center text-sm text-text-muted">
        {/* 整句进一条 key：链接文字拆出去的话，英文侧就没法把链接挪到句首/句中 */}
        <Trans
          k="page.login.signup.hint"
          slots={{
            link: (s) => (
              <Link
                to="/register"
                className="ml-1 text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim"
              >
                {s}
              </Link>
            ),
          }}
        />
      </p>
    </div>
  )
}

/** QQ 标志的简化企鹅轮廓。自绘 SVG 而不是拉腾讯的图片资源：
 *  外链图标会在网络受限时变成一个破图，且多一个第三方请求。
 *  currentColor 让它跟着按钮文字色走，深浅色主题都不用另配。 */
function QQMark() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
      <path d="M12 2c-2.9 0-5.2 2.3-5.2 5.2v1.2c-.9 1.1-1.6 2.6-1.9 4.2-.3 1.5-.1 2.6.4 2.9.4.2.9-.1 1.4-.8.2.7.6 1.3 1 1.8-.7.3-1.2.8-1.2 1.3 0 .9 1.6 1.6 3.6 1.6.8 0 1.5-.1 2.1-.3.5.1 1.1.2 1.8.2s1.3-.1 1.8-.2c.6.2 1.3.3 2.1.3 2 0 3.6-.7 3.6-1.6 0-.5-.5-1-1.2-1.3.4-.5.8-1.1 1-1.8.5.7 1 1 1.4.8.5-.3.7-1.4.4-2.9-.3-1.6-1-3.1-1.9-4.2V7.2C17.2 4.3 14.9 2 12 2z" />
    </svg>
  )
}
