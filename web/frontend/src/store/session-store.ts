/**
 * 会话状态：身份 + 后端能力开关 + BYOK key 状态。
 *
 * 页面据此决定 UI 形态，而不是各自去猜后端配置：
 *   - config.auth_enabled=false → 隐藏登录入口（开源单机形态）
 *   - keyStatus 无 key 且 key_mode=byok → 首页发起评审前先引导去填 key
 *   - config.quota_enabled=false → 隐藏配额进度条
 */

import { create } from 'zustand'
import { api, setToken } from '@/lib/apiClient'
import type { HealthConfig, Identity, KeyStatus, UsageSummary } from '@/lib/types'

interface SessionState {
  config: HealthConfig | null
  identity: Identity | null
  keyStatus: KeyStatus | null
  usage: UsageSummary | null
  loading: boolean
  error: string | null

  bootstrap: () => Promise<void>
  refreshKeys: () => Promise<void>
  refreshUsage: () => Promise<void>
  saveKey: (apiKey: string, provider?: string) => Promise<void>
  deleteKey: (provider?: string) => Promise<void>
  login: (email: string, password: string) => Promise<void>
  logout: () => void

  /** 当前是否可以发起评审（BYOK 模式下必须有 key） */
  canReview: () => boolean
}

export const useSessionStore = create<SessionState>((set, get) => ({
  config: null,
  identity: null,
  keyStatus: null,
  usage: null,
  loading: false,
  error: null,

  bootstrap: async () => {
    set({ loading: true, error: null })
    try {
      const [health, identity] = await Promise.all([api.health(), api.me()])
      set({ config: health.config, identity })
      // key/用量非关键路径，失败不该阻断启动
      await Promise.allSettled([get().refreshKeys(), get().refreshUsage()])
    } catch (e) {
      set({ error: e instanceof Error ? e.message : '后端连接失败' })
    } finally {
      set({ loading: false })
    }
  },

  refreshKeys: async () => {
    const keyStatus = await api.getKeys()
    set({ keyStatus })
  },

  refreshUsage: async () => {
    const usage = await api.usage()
    set({ usage })
  },

  saveKey: async (apiKey, provider = 'anthropic') => {
    await api.saveKey(apiKey, provider)
    await get().refreshKeys()
  },

  deleteKey: async (provider = 'anthropic') => {
    await api.deleteKey(provider)
    await get().refreshKeys()
  },

  login: async (email, password) => {
    const { token } = await api.login(email, password)
    setToken(token)
    const identity = await api.me()
    set({ identity })
    await get().refreshKeys()
  },

  logout: () => {
    setToken(null)
    set({ identity: null, keyStatus: null, usage: null })
    void get().bootstrap()
  },

  canReview: () => {
    const { config, keyStatus } = get()
    if (!config) return false
    if (config.key_mode === 'managed') return config.server_key_present
    const hasUserKey = (keyStatus?.keys?.length ?? 0) > 0
    if (config.key_mode === 'hybrid') return hasUserKey || config.server_key_present
    return hasUserKey // byok
  },
}))
