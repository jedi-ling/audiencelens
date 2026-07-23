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

  const submit = async () => {
    if (!email.trim() || !password) return
    setBusy(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate('/ask') // 落进应用而不是营销落地页
    } catch (e) {
      setError(e instanceof Error ? e.message : '登录失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <LogIn className="h-6 w-6 text-neon-green" strokeWidth={1.5} />
        <h1 className="text-xl font-semibold text-text-primary font-display">登录</h1>
        <p className="text-sm text-text-secondary">登录后可以查看完整评审报告、保存你的评审历史</p>
      </div>

      <div className="rounded-xl border border-border bg-bg-card p-6">
        <label className="block text-xs text-text-muted">邮箱</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void submit()}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-neon-green transition-colors"
          placeholder="you@example.com"
          autoFocus
        />

        <label className="mt-4 block text-xs text-text-muted">密码</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void submit()}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-neon-green transition-colors"
          placeholder="········"
        />

        {error && <p className="mt-3 text-sm text-severity-critical">{error}</p>}

        <button
          onClick={() => void submit()}
          disabled={busy || !email.trim() || !password}
          className="mt-5 w-full rounded-lg bg-neon-green py-2.5 text-sm font-semibold text-bg-primary hover:bg-neon-green-dim transition-colors disabled:opacity-50"
        >
          {busy ? '登录中…' : '登录'}
        </button>
      </div>

      <p className="mt-4 text-center text-sm text-text-muted">
        还没有账号？
        <Link to="/register" className="ml-1 text-neon-green underline underline-offset-2 hover:text-neon-green-dim">
          注册一个
        </Link>
      </p>
    </div>
  )
}
