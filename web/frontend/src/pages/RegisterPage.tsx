import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { UserPlus } from 'lucide-react'
import { useSessionStore } from '@/store/session-store'
import { t, Trans } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { tApiError } from '@/i18n/api-error'

/** 密码最短长度。同时喂给 minLength、提交前判断与 common.validate.password_min 的
 *  {{min}}——三处读同一个常量，改规则不会漏改其中一处。 */
const PASSWORD_MIN = 8

export default function RegisterPage() {
  const navigate = useNavigate()
  const register = useSessionStore((s) => s.register)
  const identity = useSessionStore((s) => s.identity)
  useDocumentTitle('page.register.meta.title')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const passwordTooShort = password.length > 0 && password.length < PASSWORD_MIN

  // 已登录还停在注册页没有意义——直接送进应用
  useEffect(() => {
    if (identity && !identity.is_anonymous) navigate('/ask', { replace: true })
  }, [identity, navigate])

  /** 走 form 的 onSubmit：回车、点按钮、密码管理器填充后提交，三条路径同一个出口。 */
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || password.length < PASSWORD_MIN || busy) return
    setBusy(true)
    setError(null)
    try {
      await register(email.trim(), password, displayName.trim() || undefined)
      navigate('/ask') // 落进应用而不是营销落地页
    } catch (err) {
      // 原先分成 ApiError / 其它两支写，两支都在把原始 message 直接显示出来。
      // tApiError 内部已经按 message_lang 判断该不该用后端原文，这里不必再分支。
      setError(tApiError(err, 'page.register.submit.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <UserPlus className="h-6 w-6 text-brand-primary" strokeWidth={1.5} />
        <h1 className="text-xl font-semibold text-text-primary font-display">
          {t('page.register.header.title')}
        </h1>
        <p className="text-sm text-text-secondary">{t('page.register.header.desc')}</p>
      </div>

      {/* 同 LoginPage：必须是真的 <form>。这一页此前更明显——只有密码框挂了
          onKeyDown，在邮箱框按回车什么都不会发生，正是"靠每个框自己挂、漏一个就不灵"。
          autoComplete 用 new-password 而不是 current-password，浏览器才会提示生成强密码。 */}
      <form onSubmit={submit} className="rounded-xl border border-border bg-bg-card p-8">
        <label htmlFor="register-name" className="block text-xs text-text-muted">
          {t('page.register.name.label')}
        </label>
        <input
          id="register-name"
          name="displayName"
          autoComplete="nickname"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder={t('page.register.name.placeholder')}
          autoFocus
        />

        <label htmlFor="register-email" className="mt-4 block text-xs text-text-muted">
          {t('page.register.email.label')}
        </label>
        <input
          id="register-email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder={t('page.register.email.placeholder')}
        />

        <label htmlFor="register-password" className="mt-4 block text-xs text-text-muted">
          {t('page.register.password.label', { min: PASSWORD_MIN })}
        </label>
        <input
          id="register-password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={PASSWORD_MIN}
          aria-describedby={passwordTooShort ? 'register-password-hint' : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder={t('page.register.password.placeholder')}
        />
        {passwordTooShort && (
          <p id="register-password-hint" className="mt-1 text-xs text-warm-orange">
            {/* 校验文案一律走 common.validate.*（契约 D11）：同一条规则在 5 个认证页 +
                设置页 + 创建评审页里逐字重复，各写各的必然有一处忘改。 */}
            {t('common.validate.password_min', { min: PASSWORD_MIN })}
          </p>
        )}

        {error && (
          <p role="alert" className="mt-3 text-sm text-severity-critical">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy || !email.trim() || password.length < PASSWORD_MIN}
          className="mt-6 flex h-11 w-full items-center justify-center rounded-lg bg-brand-primary text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors disabled:opacity-50"
        >
          {busy ? t('page.register.submit.pending') : t('page.register.submit.cta')}
        </button>

        {/* 注册前必须能看到条款。放在按钮下方而不是做成勾选框：
            这两份文档写的都是本服务真实的边界（不承诺可用率、AI 输出仅供参考），
            值得被读到，而不是被一个"我已阅读"的勾选框代替。 */}
        <p className="mt-3 text-center text-xs leading-relaxed text-text-muted">
          <Trans
            k="page.register.terms.consent"
            slots={{
              terms: (s) => (
                <Link
                  to="/terms"
                  className="mx-1 text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim"
                >
                  {s}
                </Link>
              ),
              privacy: (s) => (
                <Link
                  to="/privacy"
                  className="mx-1 text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim"
                >
                  {s}
                </Link>
              ),
            }}
          />
        </p>
      </form>

      <p className="mt-4 text-center text-sm text-text-muted">
        <Trans
          k="page.register.signin.hint"
          slots={{
            link: (s) => (
              <Link
                to="/login"
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
