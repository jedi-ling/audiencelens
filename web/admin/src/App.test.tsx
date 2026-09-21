/**
 * 登录门（App 的 gate 状态机）的单测。
 *
 * 这一层此前零覆盖，而它恰好是整个后台唯一一处"错了就把人锁在门外"的逻辑：
 * checkExistingToken 原先对**任何**失败都 setAdminToken(null)，于是后端抖一下
 * 或者返回 500，刷新页面就变成"必须重新登录"。下面 `瞬时故障不许清掉令牌`
 * 那条就是这个回归的钉子，删它之前先想清楚。
 *
 * Dashboard 里的面板一律 mock 成空组件：这里测的是门，不是仪表盘。
 * 不 mock 的话每条用例都要顺带喂一遍七八个面板的接口，测试会因为
 * "某个面板加了新请求"而红，而那和登录门毫无关系。
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import App from './App'
import { adminApi, getAdminToken, setAdminToken, setAdminUsername } from '@/lib/adminClient'
import { ApiError } from '@/lib/types'

vi.mock('@/lib/adminClient', () => ({
  adminApi: {
    overview: vi.fn(),
    login: vi.fn(),
  },
  getAdminToken: vi.fn(),
  setAdminToken: vi.fn(),
  setAdminUsername: vi.fn(),
  getAdminUsername: vi.fn(() => null),
}))

// 仪表盘里的面板：解锁后会渲染，但它们各自的请求与本文件无关。
vi.mock('@/components/OverviewCards', () => ({ OverviewCards: () => null }))
vi.mock('@/components/TimeseriesChart', () => ({ TimeseriesChart: () => null }))
vi.mock('@/components/HealthPanel', () => ({ HealthPanel: () => null }))
vi.mock('@/components/TaskTypeStatsPanel', () => ({ TaskTypeStatsPanel: () => null }))
vi.mock('@/components/CostInsightsPanel', () => ({ CostInsightsPanel: () => null }))

const mockedApi = vi.mocked(adminApi)
const mockedGetToken = vi.mocked(getAdminToken)
const mockedSetToken = vi.mocked(setAdminToken)
const mockedSetUsername = vi.mocked(setAdminUsername)

/** 解锁态的判据：头部的「锁定」按钮只有 gate === 'unlocked' 时才渲染。 */
const lockButton = () => screen.queryByRole('button', { name: '锁定' })

describe('App 登录门', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedGetToken.mockReturnValue(null)
    mockedApi.overview.mockResolvedValue(undefined as never)
  })

  it('没有存量令牌时直接显示登录表单', async () => {
    render(<App />)
    expect(await screen.findByPlaceholderText('用户名')).toBeInTheDocument()
    expect(mockedApi.overview).not.toHaveBeenCalled()
  })

  it('存量令牌验过就直接解锁，不再要求登录', async () => {
    mockedGetToken.mockReturnValue('tok')
    render(<App />)
    await waitFor(() => expect(lockButton()).toBeInTheDocument())
    expect(screen.queryByPlaceholderText('用户名')).not.toBeInTheDocument()
    expect(mockedSetToken).not.toHaveBeenCalled()
  })

  it('存量令牌被后端判为 401 时，清掉它并回到登录页', async () => {
    mockedGetToken.mockReturnValue('tok')
    mockedApi.overview.mockRejectedValue(new ApiError(401, 'unauthorized', '令牌无效'))
    render(<App />)
    expect(await screen.findByPlaceholderText('用户名')).toBeInTheDocument()
    expect(mockedSetToken).toHaveBeenCalledWith(null)
  })

  it('403 同样清掉令牌', async () => {
    mockedGetToken.mockReturnValue('tok')
    mockedApi.overview.mockRejectedValue(new ApiError(403, 'forbidden', '没有权限'))
    render(<App />)
    expect(await screen.findByPlaceholderText('用户名')).toBeInTheDocument()
    expect(mockedSetToken).toHaveBeenCalledWith(null)
  })

  // ↓↓↓ 这条是回归钉子：网络抖动 / 500 **不说明令牌失效**，清掉它等于把一次
  //     瞬时故障升级成一次凭据丢失（管理员被迫重新打一遍密码）。
  it('瞬时故障（连不上后端）不许清掉令牌，只报错并给重试', async () => {
    mockedGetToken.mockReturnValue('tok')
    mockedApi.overview.mockRejectedValue(
      new ApiError(0, 'upstream_error', '无法连接后端服务，请确认服务已启动。'),
    )
    render(<App />)

    expect(await screen.findByText('无法确认登录状态')).toBeInTheDocument()
    expect(screen.getByText('无法连接后端服务，请确认服务已启动。')).toBeInTheDocument()
    expect(mockedSetToken).not.toHaveBeenCalled()
    // 也不该把人丢回登录表单
    expect(screen.queryByPlaceholderText('用户名')).not.toBeInTheDocument()
  })

  it('500 同样保留令牌', async () => {
    mockedGetToken.mockReturnValue('tok')
    mockedApi.overview.mockRejectedValue(new ApiError(500, 'internal_error', '服务器开小差了'))
    render(<App />)
    expect(await screen.findByText('无法确认登录状态')).toBeInTheDocument()
    expect(mockedSetToken).not.toHaveBeenCalled()
  })

  it('故障态点「重试」会重新验一次；这次成功就解锁', async () => {
    mockedGetToken.mockReturnValue('tok')
    mockedApi.overview.mockRejectedValueOnce(new ApiError(500, 'internal_error', '服务器开小差了'))
    render(<App />)
    await screen.findByText('无法确认登录状态')

    mockedApi.overview.mockResolvedValue(undefined as never)
    await userEvent.click(screen.getByRole('button', { name: '重试' }))

    await waitFor(() => expect(lockButton()).toBeInTheDocument())
    expect(mockedSetToken).not.toHaveBeenCalled()
  })

  it('admin_disabled 显示「管理后台未启用」，且不清令牌', async () => {
    mockedGetToken.mockReturnValue('tok')
    mockedApi.overview.mockRejectedValue(new ApiError(503, 'admin_disabled', '未启用'))
    render(<App />)
    expect(await screen.findByText('管理后台未启用')).toBeInTheDocument()
    expect(mockedSetToken).not.toHaveBeenCalled()
  })

  it('登录成功：存下令牌与用户名，表单消失', async () => {
    mockedApi.login.mockResolvedValue({ token: 'new-tok', username: 'alice' })
    render(<App />)

    await userEvent.type(await screen.findByPlaceholderText('用户名'), 'alice')
    await userEvent.type(screen.getByPlaceholderText('密码'), 'hunter2hunter2')
    await userEvent.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => expect(lockButton()).toBeInTheDocument())
    expect(mockedApi.login).toHaveBeenCalledWith('alice', 'hunter2hunter2')
    expect(mockedSetToken).toHaveBeenCalledWith('new-tok')
    // 用户名要存下来——停用管理员账号时靠它判断"目标是不是我自己"。
    expect(mockedSetUsername).toHaveBeenCalledWith('alice')
  })

  it('密码错误：留在登录页并说清楚是密码错了', async () => {
    mockedApi.login.mockRejectedValue(new ApiError(401, 'unauthorized', 'bad credentials'))
    render(<App />)

    await userEvent.type(await screen.findByPlaceholderText('用户名'), 'alice')
    await userEvent.type(screen.getByPlaceholderText('密码'), 'wrong-password')
    await userEvent.click(screen.getByRole('button', { name: '登录' }))

    expect(await screen.findByText('用户名或密码错误')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument()
    expect(mockedSetToken).not.toHaveBeenCalled()
  })

  it('登录时后端连不上：原样显示连接错误，不谎称密码错误', async () => {
    mockedApi.login.mockRejectedValue(
      new ApiError(0, 'upstream_error', '无法连接后端服务，请确认服务已启动。'),
    )
    render(<App />)

    await userEvent.type(await screen.findByPlaceholderText('用户名'), 'alice')
    await userEvent.type(screen.getByPlaceholderText('密码'), 'hunter2hunter2')
    await userEvent.click(screen.getByRole('button', { name: '登录' }))

    expect(
      await screen.findByText('无法连接后端服务，请确认服务已启动。'),
    ).toBeInTheDocument()
    expect(screen.queryByText('用户名或密码错误')).not.toBeInTheDocument()
  })
})
