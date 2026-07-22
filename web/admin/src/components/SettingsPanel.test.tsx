import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { SettingsPanel } from './SettingsPanel'
import { adminApi } from '@/lib/adminClient'
import type { AdminSettingRow } from '@/lib/types'

vi.mock('@/lib/adminClient', () => ({
  adminApi: {
    listSettings: vi.fn(),
    setSetting: vi.fn(),
    resetSetting: vi.fn(),
  },
}))

const mocked = vi.mocked(adminApi)

function row(partial: Partial<AdminSettingRow> & Pick<AdminSettingRow, 'key' | 'label' | 'type'>): AdminSettingRow {
  return {
    choices: null,
    env_default: null,
    effective_value: null,
    overridden: false,
    ...partial,
  }
}

describe('SettingsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('AL_QUOTA_ENABLED 渲染为 checkbox 并能切换', async () => {
    mocked.listSettings.mockResolvedValue({
      settings: [
        row({
          key: 'AL_QUOTA_ENABLED',
          label: '配额总开关',
          type: 'bool',
          env_default: false,
          effective_value: false,
        }),
      ],
    })
    mocked.setSetting.mockResolvedValue({ key: 'AL_QUOTA_ENABLED', value: true })

    render(<SettingsPanel />)

    const checkbox = await screen.findByRole('checkbox')
    expect(checkbox).toBeInTheDocument()
    expect(checkbox).not.toBeChecked()

    await userEvent.click(checkbox)

    await waitFor(() => {
      expect(mocked.setSetting).toHaveBeenCalledWith('AL_QUOTA_ENABLED', true)
    })
  })

  it('AL_QUOTA_MODE 渲染为 select 并列出 plan/credits 选项', async () => {
    mocked.listSettings.mockResolvedValue({
      settings: [
        row({
          key: 'AL_QUOTA_MODE',
          label: '配额模式',
          type: 'str',
          choices: ['plan', 'credits'],
          env_default: 'plan',
          effective_value: 'plan',
        }),
      ],
    })
    mocked.setSetting.mockResolvedValue({ key: 'AL_QUOTA_MODE', value: 'credits' })

    render(<SettingsPanel />)

    const select = await screen.findByRole('combobox')
    expect(select).toBeInTheDocument()
    expect(select).toHaveValue('plan')

    const options = screen.getAllByRole('option').map((o) => o.textContent)
    expect(options).toEqual(['plan', 'credits'])

    await userEvent.selectOptions(select, 'credits')

    await waitFor(() => {
      expect(mocked.setSetting).toHaveBeenCalledWith('AL_QUOTA_MODE', 'credits')
    })
  })
})
