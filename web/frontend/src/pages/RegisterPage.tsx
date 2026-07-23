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

  const submit = async () => {
    if (!email.trim() || password.length < 8) return
    setBusy(true)
    setError(null)
    try {
      await register(email.trim(), password, displayName.trim() || undefined)
      navigate('/ask') // 落进应用而不是营销落地页
    } catch (e) {
      if (e instanceof ApiError) setError(e.message)
      else setError(e instanceof Error ? e.message : '注册失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <UserPlus className="h-6 w-6 text-neon-green" strokeWidth={1.5} />
        <h1 className="text-xl font-semibold text-text-primary font-display">注册</h1>
        <p className="text-sm text-text-secondary">不登录也能体验评审——注册只是为了解锁完整报告和历史记录</p>
      </div>

      <div className="rounded-xl border border-border bg-bg-card p-6">
        <label className="block text-xs text-text-muted">昵称（可选）</label>
        <input
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-neon-green transition-colors"
          placeholder="怎么称呼你"
          autoFocus
        />

        <label className="mt-4 block text-xs text-text-muted">邮箱</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-neon-green transition-colors"
          placeholder="you@example.com"
        />

        <label className="mt-4 block text-xs text-text-muted">密码（至少 8 位）</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void submit()}
          className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-neon-green transition-colors"
          placeholder="········"
        />
        {passwordTooShort && <p className="mt-1 text-xs text-warm-orange">密码至少需要 8 位</p>}

        {error && <p className="mt-3 text-sm text-severity-critical">{error}</p>}

        <button
          onClick={() => void submit()}
          disabled={busy || !email.trim() || password.length < 8}
          className="mt-5 w-full rounded-lg bg-neon-green py-2.5 text-sm font-semibold text-bg-primary hover:bg-neon-green-dim transition-colors disabled:opacity-50"
        >
          {busy ? '注册中…' : '注册'}
        </button>
      </div>

      <p className="mt-4 text-center text-sm text-text-muted">
        已经有账号？
        <Link to="/login" className="ml-1 text-neon-green underline underline-offset-2 hover:text-neon-green-dim">
          直接登录
        </Link>
      </p>
    </div>
  )
}
