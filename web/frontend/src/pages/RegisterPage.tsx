import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { UserPlus } from 'lucide-react'
import { ApiError } from '@/lib/apiClient'
import { useSessionStore } from '@/store/session-store'

export default function RegisterPage() {
  const navigate = useNavigate()
  const register = useSessionStore((s) => s.register)
  const identity = useSessionStore((s) => s.identity)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const passwordTooShort = password.length > 0 && password.length < 8

  // 已登录还停在注册页没有意义——直接送进应用
  useEffect(() => {
    if (identity && !identity.is_anonymous) navigate('/ask', { replace: true })
  }, [identity, navigate])

  /** 走 form 的 onSubmit：回车、点按钮、密码管理器填充后提交，三条路径同一个出口。 */
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || password.length < 8 || busy) return
    setBusy(true)
    setError(null)
    try {
      await register(email.trim(), password, displayName.trim() || undefined)
      navigate('/ask') // 落进应用而不是营销落地页
    } catch (err) {
      if (err instanceof ApiError) setError(err.message)
      else setError(err instanceof Error ? err.message : '注册失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <UserPlus className="h-6 w-6 text-brand-primary" strokeWidth={1.5} />
        <h1 className="text-xl font-semibold text-text-primary font-display">注册</h1>
        <p className="text-sm text-text-secondary">不登录也能体验评审——注册只是为了解锁完整报告和历史记录</p>
      </div>

      {/* 同 LoginPage：必须是真的 <form>。这一页此前更明显——只有密码框挂了
          onKeyDown，在邮箱框按回车什么都不会发生，正是"靠每个框自己挂、漏一个就不灵"。
          autoComplete 用 new-password 而不是 current-password，浏览器才会提示生成强密码。 */}
      <form onSubmit={submit} className="rounded-xl border border-border bg-bg-card p-6">
        <label htmlFor="register-name" className="block text-xs text-text-muted">
          昵称（可选）
        </label>
        <input
          id="register-name"
          name="displayName"
          autoComplete="nickname"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder="怎么称呼你"
          autoFocus
        />

        <label htmlFor="register-email" className="mt-4 block text-xs text-text-muted">
          邮箱
        </label>
        <input
          id="register-email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder="you@example.com"
        />

        <label htmlFor="register-password" className="mt-4 block text-xs text-text-muted">
          密码（至少 8 位）
        </label>
        <input
          id="register-password"
          name="password"
          type="password"
          autoComplete="new-password"
          minLength={8}
          aria-describedby={passwordTooShort ? 'register-password-hint' : undefined}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder="········"
        />
        {passwordTooShort && (
          <p id="register-password-hint" className="mt-1 text-xs text-warm-orange">
            密码至少需要 8 位
          </p>
        )}

        {error && (
          <p role="alert" className="mt-3 text-sm text-severity-critical">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy || !email.trim() || password.length < 8}
          className="mt-5 w-full rounded-lg bg-brand-primary py-2.5 text-sm font-semibold text-white hover:bg-brand-primary-dim transition-colors disabled:opacity-50"
        >
          {busy ? '注册中…' : '注册'}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-text-muted">
        已经有账号？
        <Link to="/login" className="ml-1 text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim">
          直接登录
        </Link>
      </p>
    </div>
  )
}
