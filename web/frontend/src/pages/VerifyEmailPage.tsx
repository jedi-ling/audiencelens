/** 邮箱验证落地页：从邮件链接进来，自动消费令牌。 */

import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { MailCheck, XCircle, Loader2 } from 'lucide-react'
import { api } from '@/lib/apiClient'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  const [state, setState] = useState<'pending' | 'ok' | 'fail'>('pending')
  const [message, setMessage] = useState('')
  // 令牌是一次性的：StrictMode 下 effect 会跑两次，第二次必然失败并把
  // 已经验证成功的页面变成"验证失败"。用 ref 保证只消费一次。
  const consumed = useRef(false)

  useEffect(() => {
    if (!token) {
      setState('fail')
      setMessage('链接不完整，缺少验证令牌')
      return
    }
    if (consumed.current) return
    consumed.current = true

    api
      .confirmVerifyEmail(token)
      .then((r) => {
        setState('ok')
        setMessage(r.email)
      })
      .catch((e) => {
        setState('fail')
        setMessage(e instanceof Error ? e.message : '验证失败')
      })
  }, [token])

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-[400px] flex-col justify-center px-4 py-12">
      <div className="rounded-xl border border-border bg-bg-card p-8 text-center">
        {state === 'pending' && (
          <>
            <Loader2 className="mx-auto h-6 w-6 animate-spin text-brand-primary" strokeWidth={1.5} />
            <p className="mt-3 text-sm text-text-secondary">正在验证…</p>
          </>
        )}

        {state === 'ok' && (
          <>
            <MailCheck className="mx-auto h-6 w-6 text-brand-primary" strokeWidth={1.5} />
            <h1 className="mt-3 text-lg font-semibold text-text-primary font-display">邮箱已验证</h1>
            <p className="mt-1 text-sm text-text-secondary">{message}</p>
            <Link
              to="/ask"
              className="mt-6 inline-block rounded-lg bg-brand-primary px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-dim"
            >
              开始评审
            </Link>
          </>
        )}

        {state === 'fail' && (
          <>
            <XCircle className="mx-auto h-6 w-6 text-severity-critical" strokeWidth={1.5} />
            <h1 className="mt-3 text-lg font-semibold text-text-primary font-display">验证未成功</h1>
            <p className="mt-1 text-sm text-text-secondary">{message}</p>
            <p className="mt-4 text-xs text-text-muted">
              验证链接 24 小时内有效且只能用一次。可到「设置」页重新发送。
            </p>
            <Link
              to="/settings"
              className="mt-5 inline-block text-sm text-brand-primary underline underline-offset-2"
            >
              去设置页
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
