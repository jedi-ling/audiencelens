/** 邮箱验证落地页：从邮件链接进来，自动消费令牌。 */

import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { MailCheck, XCircle, Loader2 } from 'lucide-react'
import { api } from '@/lib/apiClient'
import { t } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { tApiError } from '@/i18n/api-error'

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  useDocumentTitle('page.verify.meta.title')
  const [state, setState] = useState<'pending' | 'ok' | 'fail'>('pending')
  // 成功时存的是邮箱地址（与语言无关），失败时存的是**已经翻好的**一句话。
  // 已知限制（与 i18n/locales/zh/error.store.ts 记的是同一类）：失败提示在
  // 捕获那一刻定型，用户此后切换界面语言，这一句不会跟着变。要修得让这里存
  // 结构化的失败原因、由渲染处翻译；本期不做，记在交付报告里。
  const [message, setMessage] = useState('')
  // 令牌是一次性的：StrictMode 下 effect 会跑两次，第二次必然失败并把
  // 已经验证成功的页面变成"验证失败"。用 ref 保证只消费一次。
  const consumed = useRef(false)

  useEffect(() => {
    if (!token) {
      setState('fail')
      setMessage(t('page.verify.no_token.error'))
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
        setMessage(tApiError(e, 'page.verify.confirm.error'))
      })
  }, [token])

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-[400px] flex-col justify-center px-4 py-12">
      <div className="rounded-xl border border-border bg-bg-card p-8 text-center">
        {state === 'pending' && (
          <>
            <Loader2 className="mx-auto h-6 w-6 animate-spin text-brand-primary" strokeWidth={1.5} />
            <p className="mt-3 text-sm text-text-secondary">{t('page.verify.pending.loading')}</p>
          </>
        )}

        {state === 'ok' && (
          <>
            <MailCheck className="mx-auto h-6 w-6 text-brand-primary" strokeWidth={1.5} />
            <h1 className="mt-3 text-lg font-semibold text-text-primary font-display">
              {t('page.verify.ok.title')}
            </h1>
            <p className="mt-1 text-sm text-text-secondary">{message}</p>
            <Link
              to="/ask"
              className="mt-6 inline-block rounded-lg bg-brand-primary px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-dim"
            >
              {t('page.verify.ok.cta')}
            </Link>
          </>
        )}

        {state === 'fail' && (
          <>
            <XCircle className="mx-auto h-6 w-6 text-severity-critical" strokeWidth={1.5} />
            <h1 className="mt-3 text-lg font-semibold text-text-primary font-display">
              {t('page.verify.fail.title')}
            </h1>
            <p className="mt-1 text-sm text-text-secondary">{message}</p>
            <p className="mt-4 text-xs text-text-muted">{t('page.verify.fail.hint')}</p>
            <Link
              to="/settings"
              className="mt-5 inline-block text-sm text-brand-primary underline underline-offset-2"
            >
              {t('page.verify.fail.link')}
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
