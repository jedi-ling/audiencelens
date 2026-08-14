/** 用邮件里的链接重置密码。成功后不自动登录——让用户用新密码正常登录一次，
 *  免得链接被中途截获的人直接拿到会话（与后端同一口径）。 */

import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { KeyRound } from 'lucide-react'
import { api } from '@/lib/apiClient'
import { t } from '@/i18n/runtime'
import { useDocumentTitle } from '@/i18n/head'
import { tApiError } from '@/i18n/api-error'

/** 密码最短长度。同时喂给 minLength、可提交判断与 common.validate.password_min
 *  的 {{min}}，三处读同一个常量。 */
const PASSWORD_MIN = 8

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''
  useDocumentTitle('page.reset.meta.title')

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const tooShort = password.length > 0 && password.length < PASSWORD_MIN
  const mismatch = confirm.length > 0 && password !== confirm
  const canSubmit = !!token && password.length >= PASSWORD_MIN && password === confirm && !busy

  /** 走 form 的 onSubmit：回车、点按钮、密码管理器填充后提交，三条路径同一个出口
   *  （与 LoginPage / RegisterPage 同一口径）。 */
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!canSubmit) return
    setBusy(true)
    setError(null)
    try {
      await api.resetPassword(token, password)
      setDone(true)
    } catch (e) {
      setError(tApiError(e, 'page.reset.submit.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-md flex-col justify-center px-6 py-16">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <KeyRound className="h-6 w-6 text-brand-primary" strokeWidth={1.5} />
        <h1 className="text-xl font-semibold text-text-primary font-display">
          {t('page.reset.header.title')}
        </h1>
      </div>

      {/* 必须是真的 <form>：此前是「input + onKeyDown + 按钮 onClick」的拼装式提交——
          回车提交要靠每个输入框自己挂（新密码框就漏了，在那儿按回车没反应），
          浏览器/密码管理器认不出这是改密码表单（不提示保存新密码、自动填充后无法提交），
          读屏软件也拿不到表单语义。autoComplete 用 new-password，浏览器才会提示生成强密码。 */}
      <form onSubmit={submit} className="rounded-xl border border-border bg-bg-card p-6">
        {!token ? (
          <div className="text-center">
            {/* role=alert：这是"这一页现在什么也做不了"的失败态，必须被念出来 */}
            <p role="alert" className="text-sm text-severity-critical">
              {t('page.reset.no_token.error')}
            </p>
            <Link
              to="/forgot-password"
              className="mt-4 inline-block text-sm text-brand-primary underline underline-offset-2"
            >
              {t('page.reset.no_token.link')}
            </Link>
          </div>
        ) : done ? (
          <div className="text-center">
            <p className="text-sm text-text-primary">{t('page.reset.done.success')}</p>
            <p className="mt-2 text-xs text-text-muted">{t('page.reset.done.hint')}</p>
            <button
              type="button" // 在 <form> 里不写 type 就是 submit，点它会把表单再提交一次
              onClick={() => navigate('/login')}
              className="mt-6 flex h-11 w-full items-center justify-center rounded-lg bg-brand-primary text-sm font-semibold text-white transition-colors hover:bg-brand-primary-dim"
            >
              {t('page.reset.done.cta')}
            </button>
          </div>
        ) : (
          <>
            <label htmlFor="reset-password" className="block text-xs text-text-muted">
              {t('page.reset.password.label', { min: PASSWORD_MIN })}
            </label>
            <input
              id="reset-password"
              name="new-password"
              type="password"
              autoComplete="new-password"
              minLength={PASSWORD_MIN}
              aria-describedby={tooShort ? 'reset-password-hint' : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
              placeholder={t('page.reset.password.placeholder')}
              autoFocus
            />
            {tooShort && (
              <p id="reset-password-hint" className="mt-1 text-xs text-warm-orange">
                {/* 校验文案走 common.validate.*（契约 D11），与注册页同一份译文 */}
                {t('common.validate.password_min', { min: PASSWORD_MIN })}
              </p>
            )}

            <label htmlFor="reset-password-confirm" className="mt-4 block text-xs text-text-muted">
              {t('page.reset.confirm.label')}
            </label>
            <input
              id="reset-password-confirm"
              name="confirm-new-password"
              type="password"
              autoComplete="new-password"
              aria-describedby={mismatch ? 'reset-confirm-hint' : undefined}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="mt-1 w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary outline-none focus:border-brand-primary transition-colors"
              placeholder={t('page.reset.confirm.placeholder')}
            />
            {mismatch && (
              <p id="reset-confirm-hint" className="mt-1 text-xs text-warm-orange">
                {t('common.validate.password_mismatch')}
              </p>
            )}

            {/* role=alert：重置失败（链接过期等）要立刻被读屏软件念出来 */}
            {error && (
              <p role="alert" className="mt-3 text-sm text-severity-critical">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={!canSubmit}
              className="mt-6 flex h-11 w-full items-center justify-center rounded-lg bg-brand-primary text-sm font-semibold text-white transition-colors hover:bg-brand-primary-dim disabled:opacity-50"
            >
              {/* 进行中用通用词（契约 11 的判断树第 2 条）：原文就是"提交中…"，
                  没有这一页独有的语义。 */}
              {busy ? t('common.ui.submitting') : t('page.reset.submit.cta')}
            </button>
          </>
        )}
      </form>
    </div>
  )
}
