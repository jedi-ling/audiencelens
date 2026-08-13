import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { LogIn } from 'lucide-react'
import { useSessionStore } from '@/store/session-store'
import { t, Trans } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { tApiError } from '@/i18n/api-error'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useSessionStore((s) => s.login)
  const identity = useSessionStore((s) => s.identity)
  // 顺带订阅了 ui_lang（内部 useLocale），切语言时整页重新求值 t()
  useDocumentTitle('page.login.meta.title')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 已登录还停在登录页没有意义——直接送进应用
  useEffect(() => {
    if (identity && !identity.is_anonymous) navigate('/ask', { replace: true })
  }, [identity, navigate])

  /** 走 form 的 onSubmit：回车、点按钮、密码管理器自动填充后提交，三条路径同一个出口。 */
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password || busy) return
    setBusy(true)
    setError(null)
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

        {/* role=alert：登录失败是需要立刻被读屏软件念出来的，不能只是视觉上变红 */}
        {error && (
          <p role="alert" className="mt-3 text-sm text-severity-critical">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy || !email.trim() || !password}
          className="mt-6 flex h-11 w-full items-center justify-center rounded-lg bg-brand-primary text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors disabled:opacity-50"
        >
          {busy ? t('page.login.submit.pending') : t('page.login.submit.cta')}
        </button>
      </form>

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
