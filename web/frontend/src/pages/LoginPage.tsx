import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { LogIn } from 'lucide-react'
import { useSessionStore } from '@/store/session-store'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useSessionStore((s) => s.login)
  const identity = useSessionStore((s) => s.identity)

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
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <LogIn className="h-6 w-6 text-brand-primary" strokeWidth={1.5} />
        <h1 className="text-xl font-semibold text-text-primary font-display">登录</h1>
        <p className="text-sm text-text-secondary">登录后可以查看完整评审报告、保存你的评审历史</p>
      </div>

      {/* 必须是真的 <form>：此前是一堆 input + 一个 onClick 的 div 式提交，
          代价不只是"不够规范"——回车提交要靠每个输入框自己挂 onKeyDown（漏一个就不灵）、
          浏览器和密码管理器认不出这是登录表单（不提示保存、自动填充后无法提交）、
          读屏软件也拿不到表单语义。 */}
      <form onSubmit={submit} className="rounded-xl border border-white/[0.08] bg-black/30 p-6">
        <label htmlFor="login-email" className="block text-xs text-text-muted">
          邮箱
        </label>
        <input
          id="login-email"
          name="email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder="you@example.com"
          autoFocus
        />

        <label htmlFor="login-password" className="mt-4 block text-xs text-text-muted">
          密码
        </label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
          placeholder="········"
        />

        <div className="mt-2 text-right">
          <Link
            to="/forgot-password"
            className="text-xs text-text-muted underline underline-offset-2 hover:text-brand-primary"
          >
            忘记密码？
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
          {busy ? '登录中…' : '登录'}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-text-muted">
        还没有账号？
        <Link to="/register" className="ml-1 text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim">
          注册一个
        </Link>
      </p>
    </div>
  )
}
