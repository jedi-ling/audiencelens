/**
 * 邮件发送面板：看清当前配置 + 当场打一封真信验证。
 *
 * 为什么需要它：邮件配错的表现是「什么都不发生」--默认 console 档不报错、
 * 注册接口照样返回 200，只有用户收不到激活信。发一封测试邮件可以当场验证。
 *
 * 这里不走 adminClient：只借它的 getAdminToken（令牌存放口径要一致），
 * 请求逻辑自己实现，避免为一个面板去动共享的 API 客户端。
 */

import { useCallback, useEffect, useState } from 'react'
import { Mail, Loader2, CheckCircle2, XCircle, AlertTriangle, Send } from 'lucide-react'
import { getAdminToken } from '@/lib/adminClient'

const BASE = (import.meta.env.VITE_API_BASE as string) || ''

/** 与后端 mail_service.describe_config() 一一对应。 */
type MailConfig = {
  configured_backend: string
  effective_backend: string
  really_sends: boolean
  mail_from: string
  smtp_host: string | null
  smtp_port: number
  smtp_use_ssl: boolean
  smtp_user: string | null
  smtp_password_set: boolean
  smtp_timeout_seconds: number
  public_web_url: string
  outbox_dir: string | null
  auth_enabled: boolean
}

type TestResult = MailConfig & {
  ok: boolean
  delivered?: boolean
  to?: string
  message?: string
  warning?: string
  error?: string
}

async function adminFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body) headers.set('Content-Type', 'application/json')
  const token = getAdminToken()
  if (token) headers.set('X-Admin-Token', token)

  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers })
  } catch {
    throw new Error('无法连接后端服务，请确认服务已启动。')
  }
  const text = await res.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = null
  }
  if (!res.ok) {
    const err = (body as { error?: { message: string } })?.error
    throw new Error(err?.message ?? `请求失败（HTTP ${res.status}）`)
  }
  return body as T
}

function Row({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="w-28 shrink-0 text-text-muted">{label}</span>
      <span className={`break-all font-mono ${warn ? 'text-warm-orange' : 'text-text-secondary'}`}>
        {value}
      </span>
    </div>
  )
}

export function MailPanel() {
  const [config, setConfig] = useState<MailConfig | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [to, setTo] = useState('')
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState<TestResult | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setConfig(await adminFetch<MailConfig>('/api/admin/mail/status'))
      setLoadError(null)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const sendTest = async () => {
    if (!to.trim()) return
    setSending(true)
    setResult(null)
    setSendError(null)
    try {
      const res = await adminFetch<TestResult>('/api/admin/mail/test', {
        method: 'POST',
        body: JSON.stringify({ to: to.trim() }),
      })
      setResult(res)
      setConfig(res) // 响应里带着最新配置快照，顺手刷新上面的状态区
    } catch (e) {
      setSendError(e instanceof Error ? e.message : '发送失败')
    } finally {
      setSending(false)
    }
  }

  const blindSpot = config && !config.really_sends

  return (
    <section className="rounded-xl border border-border bg-bg-card p-5">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
        <Mail className="h-4 w-4 text-brand-primary" strokeWidth={1.5} />
        邮件发送
        <span className="font-mono text-[10px] font-normal text-text-muted">
          邮箱验证 / 密码重置走这条链路
        </span>
      </h2>
      <p className="mt-1 text-xs text-text-muted">
        邮件配错时注册接口仍返回成功，但用户收不到激活信。配置后请发一封测试邮件验证。
      </p>

      {loadError && <p className="mt-3 font-mono text-xs text-severity-critical">{loadError}</p>}

      {config && (
        <>
          {blindSpot ? (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-warm-orange/40 bg-warm-orange/10 px-4 py-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warm-orange" strokeWidth={1.5} />
              <div className="text-xs text-text-secondary">
                <p className="font-semibold text-warm-orange">
                  当前是 {config.effective_backend} 档：用户收不到任何邮件
                </p>
                <p className="mt-1">
                  {config.configured_backend === 'smtp'
                    ? '已设 AL_MAIL_BACKEND=smtp，但 AL_SMTP_HOST 为空，实际回落到了 console。'
                    : '邮箱验证与密码重置邮件不会真的发出——注册后激活不了、密码忘了找不回。'}
                  {config.auth_enabled
                    ? ' 账号体系已开启，这条必须修。'
                    : ' 当前未开启账号体系，暂时不影响用户。'}
                </p>
                {config.outbox_dir && (
                  <p className="mt-1 font-mono text-[11px] text-text-muted break-all">
                    完整邮件（含令牌）落在服务器本地：{config.outbox_dir}
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="mt-4 flex items-center gap-2 rounded-lg border border-brand-primary/30 bg-bg-primary px-4 py-3 font-mono text-xs text-brand-primary">
              <CheckCircle2 className="h-4 w-4 shrink-0" strokeWidth={1.5} />
              SMTP 已配置，邮件会真的发出。是否送达仍以下面的测试为准。
            </div>
          )}

          <div className="mt-4 space-y-1.5 text-xs">
            <Row label="后端" value={`${config.configured_backend} → 实际 ${config.effective_backend}`} warn={config.configured_backend !== config.effective_backend} />
            <Row label="发件人" value={config.mail_from} warn={config.mail_from.includes('@localhost')} />
            <Row
              label="SMTP"
              value={
                config.smtp_host
                  ? `${config.smtp_host}:${config.smtp_port}（${config.smtp_use_ssl ? 'SSL' : 'STARTTLS'}，超时 ${config.smtp_timeout_seconds}s）`
                  : '未配置'
              }
              warn={!config.smtp_host}
            />
            <Row label="SMTP 账号" value={config.smtp_user ?? '未配置'} />
            <Row label="SMTP 密码" value={config.smtp_password_set ? '已设置' : '未设置'} warn={!!config.smtp_user && !config.smtp_password_set} />
            <Row label="站点地址" value={config.public_web_url} />
          </div>
        </>
      )}

      <div className="mt-4 flex gap-2">
        <input
          type="email"
          value={to}
          onChange={(e) => {
            setTo(e.target.value)
            setResult(null)
            setSendError(null)
          }}
          onKeyDown={(e) => e.key === 'Enter' && void sendTest()}
          aria-label="测试邮件地址"
          placeholder="收测试邮件的地址，填一个你能立刻打开的邮箱"
          className="w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 font-mono text-sm text-text-primary placeholder-text-muted outline-none focus:border-brand-primary transition-colors"
        />
        <button
          onClick={() => void sendTest()}
          disabled={sending || !to.trim()}
          className="flex shrink-0 items-center gap-1.5 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-bg-primary hover:bg-brand-primary-dim transition-colors disabled:opacity-50"
        >
          {sending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />
          ) : (
            <Send className="h-3.5 w-3.5" strokeWidth={1.5} />
          )}
          发送测试邮件
        </button>
      </div>

      {sendError && (
        <div className="mt-2 flex items-start gap-2 font-mono text-xs text-severity-critical">
          <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
          <span className="break-all">{sendError}</span>
        </div>
      )}

      {result?.ok === false && (
        <div className="mt-2 flex items-start gap-2 font-mono text-xs text-severity-critical">
          <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
          <span className="break-all">{result.error}</span>
        </div>
      )}

      {result?.ok && result.delivered && (
        <div className="mt-2 flex items-start gap-2 font-mono text-xs text-brand-primary">
          <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
          <span className="break-all">{result.message}</span>
        </div>
      )}

      {result?.ok && !result.delivered && (
        <div className="mt-2 flex items-start gap-2 font-mono text-xs text-warm-orange">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={1.5} />
          <span className="break-all">{result.warning}</span>
        </div>
      )}
    </section>
  )
}
