import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { PlansPanel } from './PlansPanel'
import { adminApi } from '@/lib/adminClient'
import type { AdminPlan } from '@/lib/types'

vi.mock('@/lib/adminClient', () => ({
  adminApi: {
    plans: vi.fn(),
    setPlanField: vi.fn(),
    resetPlanField: vi.fn(),
  },
}))

const mocked = vi.mocked(adminApi)

const basePlan: AdminPlan = {
  id: 'pro',
  name: 'Pro',
  price_usd_month: 20,
  reviews_per_day: 30,
  cost_usd_per_day: 5,
  overridden_fields: [],
  editable_fields: ['price_usd_month', 'reviews_per_day', 'cost_usd_per_day'],
  env_default: { price_usd_month: 20, reviews_per_day: 30, cost_usd_per_day: 5 },
}

describe('PlansPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染三个可编辑字段标签：月价 / 每日评审上限 / 每日成本上限', async () => {
    mocked.plans.mockResolvedValue({ plans: [basePlan] })

    render(<PlansPanel />)

    expect(await screen.findByText('月价 (USD)')).toBeInTheDocument()
    expect(screen.getByText('每日评审上限')).toBeInTheDocument()
    expect(screen.getByText('每日成本上限 (USD)')).toBeInTheDocument()
  })

  it('编辑 price_usd_month 失焦时调用 setPlanField', async () => {
    mocked.plans.mockResolvedValue({ plans: [basePlan] })
    mocked.setPlanField.mockResolvedValue({
      ...basePlan,
      price_usd_month: 25,
      overridden_fields: ['price_usd_month'],
    })

    render(<PlansPanel />)

    const label = await screen.findByText('月价 (USD)')
    const input = label.parentElement?.querySelector('input') as HTMLInputElement
    expect(input).toBeInTheDocument()
    expect(input).toHaveValue(20)

    await userEvent.clear(input)
    await userEvent.type(input, '25')
    await userEvent.tab() // 触发 blur

    await waitFor(() => {
      expect(mocked.setPlanField).toHaveBeenCalledWith('pro', 'price_usd_month', 25)
    })
  })

  it('编辑 reviews_per_day 失焦时调用 setPlanField', async () => {
    mocked.plans.mockResolvedValue({ plans: [basePlan] })
    mocked.setPlanField.mockResolvedValue({
      ...basePlan,
      reviews_per_day: 50,
      overridden_fields: ['reviews_per_day'],
    })

    render(<PlansPanel />)

    const label = await screen.findByText('每日评审上限')
    const input = label.parentElement?.querySelector('input') as HTMLInputElement
    expect(input).toHaveValue(30)

    await userEvent.clear(input)
    await userEvent.type(input, '50')
    await userEvent.tab()

    await waitFor(() => {
      expect(mocked.setPlanField).toHaveBeenCalledWith('pro', 'reviews_per_day', 50)
    })
  })

  it('编辑 cost_usd_per_day 失焦时调用 setPlanField', async () => {
    mocked.plans.mockResolvedValue({ plans: [basePlan] })
    mocked.setPlanField.mockResolvedValue({
      ...basePlan,
      cost_usd_per_day: 8,
      overridden_fields: ['cost_usd_per_day'],
    })

    render(<PlansPanel />)

    const label = await screen.findByText('每日成本上限 (USD)')
    const input = label.parentElement?.querySelector('input') as HTMLInputElement
    expect(input).toHaveValue(5)

    await userEvent.clear(input)
    await userEvent.type(input, '8')
    await userEvent.tab()

    await waitFor(() => {
      expect(mocked.setPlanField).toHaveBeenCalledWith('pro', 'cost_usd_per_day', 8)
    })
  })

  it('已覆盖字段显示重置按钮并调用 resetPlanField', async () => {
    mocked.plans.mockResolvedValue({
      plans: [{ ...basePlan, overridden_fields: ['price_usd_month'] }],
    })
    mocked.resetPlanField.mockResolvedValue(basePlan)

    render(<PlansPanel />)

    const resetBtn = await screen.findByRole('button', { name: '重置' })
    await userEvent.click(resetBtn)

    await waitFor(() => {
      expect(mocked.resetPlanField).toHaveBeenCalledWith('pro', 'price_usd_month')
    })
  })

  it('free 档非可编辑限额渲染为只读生效值并指向设置页，不给输入框', async () => {
    // 后端契约：free 的每日限额由设置页 quota_free_* 管理，editable_fields 只剩月价，
    // 但返回值里的 reviews_per_day / cost_usd_per_day 是真实生效值，面板要只读展示。
    mocked.plans.mockResolvedValue({
      plans: [{
        ...basePlan,
        id: 'free',
        name: 'Free',
        price_usd_month: 0,
        reviews_per_day: 3,
        cost_usd_per_day: 0.5,
        editable_fields: ['price_usd_month'],
        env_default: { price_usd_month: 0 },
      }],
    })

    render(<PlansPanel />)

    // 三个字段标签都在（缺项不是隐藏，是只读）
    expect(await screen.findByText('每日评审上限')).toBeInTheDocument()
    expect(screen.getByText('每日成本上限 (USD)')).toBeInTheDocument()

    // 只读字段：显示生效值 + 设置页指引，且它所在块里没有 input
    const dailyLabel = screen.getByText('每日评审上限')
    const block = dailyLabel.parentElement as HTMLElement
    expect(block.textContent).toContain('3')
    expect(block.querySelector('input')).toBeNull()
    expect(screen.getAllByText('在「设置」页调整')).toHaveLength(2)

    // 可编辑的月价仍然是输入框
    const priceLabel = screen.getByText('月价 (USD)')
    expect(priceLabel.parentElement?.parentElement?.querySelector('input')).not.toBeNull()
  })
})
