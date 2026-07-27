/**
 * MailPanel 的验收点只有两条，但都是"这个按钮不是装饰"的证据：
 *   1. 点击后真的发出了 POST /api/admin/mail/test（带管理员令牌）；
 *   2. console 档返回 delivered=false 时，界面明说"没发出去"而不是显示成功。
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'
import { MailPanel } from './MailPanel'

vi.mock('@/lib/adminClient', () => ({
  getAdminToken: () => 'test-admin-token',
}))

const SMTP_STATUS = {
  configured_backend: 'smtp',
  effective_backend: 'smtp',
  really_sends: true,
  mail_from: 'AudienceLens <noreply@example.com>',
  smtp_host: 'smtp.example.com',
  smtp_port: 465,
  smtp_use_ssl: true,
  smtp_user: 'noreply@example.com',
  smtp_password_set: true,
  smtp_timeout_seconds: 15,
  public_web_url: 'https://example.com',
  outbox_dir: null,
  auth_enabled: true,
}

const CONSOLE_STATUS = {
  ...SMTP_STATUS,
  configured_backend: 'console',
  effective_backend: 'console',
  really_sends: false,
  smtp_host: null,
  outbox_dir: '/app/data/outbox',
}

function mockFetch(handlers: Record<string, unknown>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    void init
    const key = Object.keys(handlers).find((k) => String(url).includes(k))
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify(handlers[key!]),
    } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('MailPanel', () => {
  beforeEach(() => vi.clearAllMocks())
  afterEach(() => vi.unstubAllGlobals())

  it('console 档时显著警告「用户收不到任何邮件」', async () => {
    mockFetch({ '/mail/status': CONSOLE_STATUS })
    render(<MailPanel />)
    expect(await screen.findByText(/用户收不到任何邮件/)).toBeInTheDocument()
    expect(screen.getByText(/\/app\/data\/outbox/)).toBeInTheDocument()
  })

  it('点击真的发出 POST /api/admin/mail/test，并带上管理员令牌', async () => {
    const fetchMock = mockFetch({
      '/mail/status': SMTP_STATUS,
      '/mail/test': { ...SMTP_STATUS, ok: true, delivered: true, message: '已通过 SMTP 投递给 ops@example.com。' },
    })
    render(<MailPanel />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    await userEvent.type(screen.getByPlaceholderText(/收测试邮件的地址/), 'ops@example.com')
    await userEvent.click(screen.getByRole('button', { name: /发送测试邮件/ }))

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([url]) => String(url).includes('/mail/test'))
      expect(call).toBeDefined()
      const init = call![1] as unknown as RequestInit
      expect(init.method).toBe('POST')
      expect(JSON.parse(init.body as string)).toEqual({ to: 'ops@example.com' })
      expect((init.headers as Headers).get('X-Admin-Token')).toBe('test-admin-token')
    })
    expect(await screen.findByText(/已通过 SMTP 投递/)).toBeInTheDocument()
  })

  it('console 档发"成功"时显示的是警告而不是绿色成功', async () => {
    mockFetch({
      '/mail/status': CONSOLE_STATUS,
      '/mail/test': {
        ...CONSOLE_STATUS,
        ok: true,
        delivered: false,
        warning: '当前是 console 档，邮件**没有真的发出**。',
      },
    })
    render(<MailPanel />)
    await userEvent.type(await screen.findByPlaceholderText(/收测试邮件的地址/), 'ops@example.com')
    await userEvent.click(screen.getByRole('button', { name: /发送测试邮件/ }))

    expect(await screen.findByText(/没有真的发出/)).toBeInTheDocument()
  })

  it('失败时把后端给的可读原因原样显示出来', async () => {
    mockFetch({
      '/mail/status': SMTP_STATUS,
      '/mail/test': {
        ...SMTP_STATUS,
        ok: false,
        error: 'SMTP 认证失败 @ smtp.example.com:465（SSL）：535 auth failed。多数邮箱服务商这里要填的是授权码。',
      },
    })
    render(<MailPanel />)
    await userEvent.type(await screen.findByPlaceholderText(/收测试邮件的地址/), 'ops@example.com')
    await userEvent.click(screen.getByRole('button', { name: /发送测试邮件/ }))

    expect(await screen.findByText(/SMTP 认证失败/)).toBeInTheDocument()
  })
})
