/**
 * 忘记密码：申请重置链接。
 *
 * 无论邮箱是否注册过，界面都显示同样的成功文案——后端本来就不区分
 * （防邮箱枚举），前端要是按"找到了/没找到"分支显示，等于把后端刻意
 * 抹掉的信息又泄露回去。
 */

import { useState } from 'react'
import { Link } from 'react-router'
import { KeyRound } from 'lucide-react'
import { api } from '@/lib/apiClient'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!email.trim()) return
    setBusy(true)
    setError(null)
    try {
      await api.forgotPassword(email.trim())
      setSent(true)
    } catch (e) {
      setError(e instanceof Error ? e.message : '发送失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <KeyRound className="h-6 w-6 text-neon-green" strokeWidth={1.5} />
        <h1 className="text-xl font-semibold text-text-primary font-display">找回密码</h1>
        <p className="text-sm text-text-secondary">输入注册邮箱，我们会发一个重置链接给你</p>
      </div>

      <div className="rounded-xl border border-border bg-bg-card p-6">
        {sent ? (
          <div className="text-center">
            <p className="text-sm text-text-primary">如果该邮箱已注册，重置链接已经发出。</p>
            <p className="mt-2 text-xs text-text-muted">
              链接 60 分钟内有效，只能使用一次。没收到请检查垃圾邮件箱。
            </p>
            <Link
              to="/login"
              className="mt-5 inline-block text-sm text-neon-green underline underline-offset-2 hover:text-neon-green-dim"
            >
              返回登录
            </Link>
          </div>
        ) : (
          <>
            <label className="block text-xs text-text-muted">注册邮箱</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void submit()}
              className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-neon-green transition-colors"
              placeholder="you@example.com"
              autoFocus
            />

            {error && <p className="mt-3 text-sm text-severity-critical">{error}</p>}

            <button
              onClick={() => void submit()}
              disabled={busy || !email.trim()}
              className="mt-5 w-full rounded-lg bg-neon-green py-2.5 text-sm font-semibold text-bg-primary transition-colors hover:bg-neon-green-dim disabled:opacity-50"
            >
              {busy ? '发送中…' : '发送重置链接'}
            </button>
          </>
        )}
      </div>

      <p className="mt-4 text-center text-sm text-text-muted">
        想起来了？
        <Link to="/login" className="ml-1 text-neon-green underline underline-offset-2 hover:text-neon-green-dim">
          直接登录
        </Link>
      </p>
    </div>
  )
}
