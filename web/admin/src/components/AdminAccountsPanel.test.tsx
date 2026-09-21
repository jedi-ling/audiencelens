/**
 * 管理员账号面板的单测，重点在「停用」这个不可逆动作上。
 *
 * 停用会让目标账号已签发的会话立刻失效。此前**点一下就执行**，而且完全允许
 * 停掉自己、或者停掉最后一个启用中的账号——后者的后果是没有人能再登进后台。
 * 下面三条（不立刻调接口 / 是你自己要警告 / 最后一个要警告）就是这些行为的钉子。
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { AdminAccountsPanel } from './AdminAccountsPanel'
import { adminApi, getAdminUsername } from '@/lib/adminClient'

vi.mock('@/lib/adminClient', () => ({
  adminApi: {
    listAdminUsers: vi.fn(),
    createAdminUser: vi.fn(),
    deactivateAdminUser: vi.fn(),
  },
  getAdminUsername: vi.fn(() => null),
}))

const mockedApi = vi.mocked(adminApi)
const mockedGetUsername = vi.mocked(getAdminUsername)

interface Row {
  id: string
  username: string
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

function row(partial: Partial<Row> & Pick<Row, 'id' | 'username'>): Row {
  return {
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    last_login_at: null,
    ...partial,
  }
}

/** 找到某个用户名所在的那一行（<tr>），用来把断言限定在这一行里。 */
function rowOf(username: string): HTMLElement {
  return screen.getByText(username).closest('tr') as HTMLElement
}

describe('AdminAccountsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedGetUsername.mockReturnValue(null)
    mockedApi.deactivateAdminUser.mockResolvedValue({ ok: true })
  })

  it('渲染账号列表与状态', async () => {
    mockedApi.listAdminUsers.mockResolvedValue([
      row({ id: '1', username: 'alice' }),
      row({ id: '2', username: 'bob', is_active: false }),
    ])
    render(<AdminAccountsPanel />)

    expect(await screen.findByText('alice')).toBeInTheDocument()
    expect(within(rowOf('alice')).getByText('启用')).toBeInTheDocument()
    expect(within(rowOf('bob')).getByText('已停用')).toBeInTheDocument()
    // 已停用的账号不该再有停用按钮
    expect(within(rowOf('bob')).queryByRole('button', { name: '停用' })).not.toBeInTheDocument()
  })

  it('点「停用」不会立刻调接口，而是先要一次确认', async () => {
    mockedApi.listAdminUsers.mockResolvedValue([
      row({ id: '1', username: 'alice' }),
      row({ id: '2', username: 'bob' }),
    ])
    render(<AdminAccountsPanel />)

    await userEvent.click(within(rowOf(await findUser('alice'))).getByRole('button', { name: '停用' }))

    expect(mockedApi.deactivateAdminUser).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: '确认停用' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '取消' })).toBeInTheDocument()
  })

  it('确认之后才真的停用', async () => {
    mockedApi.listAdminUsers.mockResolvedValue([
      row({ id: '1', username: 'alice' }),
      row({ id: '2', username: 'bob' }),
    ])
    render(<AdminAccountsPanel />)

    await userEvent.click(within(rowOf(await findUser('alice'))).getByRole('button', { name: '停用' }))
    await userEvent.click(screen.getByRole('button', { name: '确认停用' }))

    await waitFor(() => expect(mockedApi.deactivateAdminUser).toHaveBeenCalledWith('1'))
  })

  it('取消之后什么都不发生，确认按钮收回去', async () => {
    mockedApi.listAdminUsers.mockResolvedValue([
      row({ id: '1', username: 'alice' }),
      row({ id: '2', username: 'bob' }),
    ])
    render(<AdminAccountsPanel />)

    await userEvent.click(within(rowOf(await findUser('alice'))).getByRole('button', { name: '停用' }))
    await userEvent.click(screen.getByRole('button', { name: '取消' }))

    expect(mockedApi.deactivateAdminUser).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: '确认停用' })).not.toBeInTheDocument()
  })

  it('停用的是当前登录账号时，明说"你自己会被踢出去"', async () => {
    mockedGetUsername.mockReturnValue('alice')
    mockedApi.listAdminUsers.mockResolvedValue([
      row({ id: '1', username: 'alice' }),
      row({ id: '2', username: 'bob' }),
    ])
    render(<AdminAccountsPanel />)

    await userEvent.click(within(rowOf(await findUser('alice'))).getByRole('button', { name: '停用' }))

    expect(
      screen.getByText('这是你当前登录的账号——确认后你自己会被立刻踢出后台。'),
    ).toBeInTheDocument()
  })

  it('停用别人时不会出现"这是你自己"的警告', async () => {
    mockedGetUsername.mockReturnValue('alice')
    mockedApi.listAdminUsers.mockResolvedValue([
      row({ id: '1', username: 'alice' }),
      row({ id: '2', username: 'bob' }),
    ])
    render(<AdminAccountsPanel />)

    await userEvent.click(within(rowOf(await findUser('bob'))).getByRole('button', { name: '停用' }))

    expect(
      screen.queryByText('这是你当前登录的账号——确认后你自己会被立刻踢出后台。'),
    ).not.toBeInTheDocument()
  })

  it('这是最后一个启用中的账号时，明说没人能再登进来', async () => {
    mockedApi.listAdminUsers.mockResolvedValue([
      row({ id: '1', username: 'alice' }),
      row({ id: '2', username: 'bob', is_active: false }),
    ])
    render(<AdminAccountsPanel />)

    await userEvent.click(within(rowOf(await findUser('alice'))).getByRole('button', { name: '停用' }))

    expect(
      screen.getByText(/这是最后一个启用中的管理员账号/),
    ).toBeInTheDocument()
  })

  it('还有别的启用账号时不报"最后一个"', async () => {
    mockedApi.listAdminUsers.mockResolvedValue([
      row({ id: '1', username: 'alice' }),
      row({ id: '2', username: 'bob' }),
    ])
    render(<AdminAccountsPanel />)

    await userEvent.click(within(rowOf(await findUser('alice'))).getByRole('button', { name: '停用' }))

    expect(screen.queryByText(/这是最后一个启用中的管理员账号/)).not.toBeInTheDocument()
  })

  it('停用失败时把后端的话显示出来，且不假装已经停用', async () => {
    mockedApi.listAdminUsers.mockResolvedValue([
      row({ id: '1', username: 'alice' }),
      row({ id: '2', username: 'bob' }),
    ])
    mockedApi.deactivateAdminUser.mockRejectedValue(new Error('不能停用最后一个管理员'))
    render(<AdminAccountsPanel />)

    await userEvent.click(within(rowOf(await findUser('alice'))).getByRole('button', { name: '停用' }))
    await userEvent.click(screen.getByRole('button', { name: '确认停用' }))

    expect(await screen.findByText('不能停用最后一个管理员')).toBeInTheDocument()
  })
})

/** 等列表渲染出来再返回用户名，省得每条用例都写一遍 findByText。 */
async function findUser(username: string): Promise<string> {
  await screen.findByText(username)
  return username
}
