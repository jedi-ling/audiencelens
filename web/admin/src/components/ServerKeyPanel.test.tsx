import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { ServerKeyPanel } from './ServerKeyPanel'
import { adminApi } from '@/lib/adminClient'

vi.mock('@/lib/adminClient', () => ({
  adminApi: {
    serverKeyStatus: vi.fn(),
    setServerKey: vi.fn(),
    testServerKey: vi.fn(),
    deleteServerKey: vi.fn(),
  },
}))

const mocked = vi.mocked(adminApi)

describe('ServerKeyPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocked.serverKeyStatus.mockResolvedValue({ configured: false, key: null })
  })

  it('Anthropic 表单包含模型 ID、API Base、API Key 三个输入', async () => {
    render(<ServerKeyPanel />)

    // 等初次加载完成，避免与后续状态变更竞争
    await waitFor(() => expect(mocked.serverKeyStatus).toHaveBeenCalledWith('anthropic'))

    expect(screen.getByPlaceholderText(/模型 ID，留空自动按人格分级选型/)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/API Base，留空用官方地址/)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/sk-ant-/)).toBeInTheDocument()
  })

  it('保存按钮把 key/provider/model/apiBase 一起提交', async () => {
    mocked.setServerKey.mockResolvedValue({
      provider: 'anthropic',
      model: 'claude-opus-4',
      api_base: 'https://proxy.example.com',
      masked: 'sk-ant-***',
    })

    render(<ServerKeyPanel />)
    await waitFor(() => expect(mocked.serverKeyStatus).toHaveBeenCalled())

    await userEvent.type(screen.getByPlaceholderText(/模型 ID，留空自动按人格分级选型/), 'claude-opus-4')
    await userEvent.type(screen.getByPlaceholderText(/API Base，留空用官方地址/), 'https://proxy.example.com')
    await userEvent.type(screen.getByPlaceholderText(/sk-ant-/), 'sk-ant-test-key')

    await userEvent.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => {
      expect(mocked.setServerKey).toHaveBeenCalledWith('sk-ant-test-key', 'anthropic', {
        model: 'claude-opus-4',
        apiBase: 'https://proxy.example.com',
      })
    })
  })

  it('切到 OpenAI 兼容时未填模型名称会阻止保存并提示', async () => {
    render(<ServerKeyPanel />)
    await waitFor(() => expect(mocked.serverKeyStatus).toHaveBeenCalled())

    await userEvent.click(screen.getByRole('button', { name: /OpenAI 兼容/ }))
    await userEvent.type(screen.getByPlaceholderText(/对应服务商的 API Key/), 'any-key')
    await userEvent.click(screen.getByRole('button', { name: '保存' }))

    expect(await screen.findByText(/需要填写模型名称/)).toBeInTheDocument()
    expect(mocked.setServerKey).not.toHaveBeenCalled()
  })
})
