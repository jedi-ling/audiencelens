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
import { t, Trans } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { tApiError } from '@/i18n/api-error'

export default function ForgotPasswordPage() {
  useDocumentTitle('page.forgot.meta.title')
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /** 走 form 的 onSubmit：回车、点按钮、密码管理器填充后提交，三条路径同一个出口
   *  （与 LoginPage / RegisterPage 同一口径）。 */
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || busy) return
    setBusy(true)
    setError(null)
    try {
      await api.forgotPassword(email.trim())
      setSent(true)
    } catch (e) {
      setError(tApiError(e, 'page.forgot.submit.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <KeyRound className="h-6 w-6 text-brand-primary" strokeWidth={1.5} />
        <h1 className="text-xl font-semibold text-text-primary font-display">
          {t('page.forgot.header.title')}
        </h1>
        <p className="text-sm text-text-secondary">{t('page.forgot.header.desc')}</p>
      </div>

      {/* 必须是真的 <form>：此前是「input + onKeyDown + 按钮 onClick」的拼装式提交，
          代价是浏览器/密码管理器认不出这是账号相关表单（不自动填邮箱），
          读屏软件也拿不到表单语义。这一页只有一个字段，更没有理由不用 form。 */}
      <form onSubmit={submit} className="rounded-xl border border-border bg-bg-card p-8">
        {sent ? (
          <div className="text-center">
            <p className="text-sm text-text-primary">{t('page.forgot.sent.success')}</p>
            <p className="mt-2 text-xs text-text-muted">{t('page.forgot.sent.hint')}</p>
            <Link
              to="/login"
              className="mt-5 inline-block text-sm text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim"
            >
              {t('page.forgot.sent.link')}
            </Link>
          </div>
        ) : (
          <>
            <label htmlFor="forgot-email" className="block text-xs text-text-muted">
              {t('page.forgot.email.label')}
            </label>
            <input
              id="forgot-email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
              placeholder={t('page.forgot.email.placeholder')}
              autoFocus
            />

            {/* role=alert：发送失败要立刻被读屏软件念出来，不能只是视觉上变红 */}
            {error && (
              <p role="alert" className="mt-3 text-sm text-severity-critical">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy || !email.trim()}
              className="mt-5 w-full rounded-lg bg-brand-primary py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-dim disabled:opacity-50"
            >
              {/* 进行中用通用词（契约 11 的判断树第 2 条）：这里的"发送中…"没有
                  任何这一页独有的语义，各页各写会攒出 5 种省略号写法。 */}
              {busy ? t('common.ui.sending') : t('page.forgot.submit.cta')}
            </button>
          </>
        )}
      </form>

      <p className="mt-4 text-center text-sm text-text-muted">
        <Trans
          k="page.forgot.signin.hint"
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
