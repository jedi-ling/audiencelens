/**
 * 会话状态：身份 + 后端能力开关 + BYOK key 状态。
 *
 * 页面据此决定 UI 形态，而不是各自去猜后端配置：
 *   - config.auth_enabled=false → 隐藏登录入口（开源单机形态）
 *   - keyStatus 无 key 且 key_mode=byok → 首页发起评审前先引导去填 key
 *   - config.quota_enabled=false → 隐藏配额进度条
 */

import { create } from 'zustand'
import { api, claimPendingReviews, getToken, setToken } from '@/lib/apiClient'
import type { HealthConfig, Identity, KeyStatus, UsageSummary } from '@/lib/types'

interface SessionState {
  config: HealthConfig | null
  identity: Identity | null
  keyStatus: KeyStatus | null
  usage: UsageSummary | null
  loading: boolean
  error: string | null
  /** localStorage 里存着 token、但后端把它当无效/过期处理（判定依据：
   * /auth/me 静默退回匿名身份而不是报错——见 app/deps.py optional_identity）。
   * 区别于"本来就没登录"，这种情况要提示用户，而不是既不报错也不解释地
   * 让人以为自己账户突然消失了。 */
  sessionExpired: boolean
  dismissSessionExpired: () => void

  bootstrap: () => Promise<void>
  refreshKeys: () => Promise<void>
  refreshUsage: () => Promise<void>
  saveKey: (apiKey: string, provider?: string) => Promise<void>
  deleteKey: (provider?: string) => Promise<void>
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName?: string) => Promise<void>
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
  sessionExpired: false,
  dismissSessionExpired: () => set({ sessionExpired: false }),

  bootstrap: async () => {
    set({ loading: true, error: null })
    // 进来时先记下"本地是否存着一把 token"——如果有，但下面拿到的身份是匿名，
    // 说明这把 token 被后端拒绝了（过期/失效），而不是用户压根没登录过。
    const hadToken = !!getToken()
    try {
      const [health, identity] = await Promise.all([api.health(), api.me()])
      set({ config: health.config, identity })
      if (hadToken && identity.is_anonymous) {
        setToken(null) // 过期 token 留着没用，还会在后续请求里继续带上
        set({ sessionExpired: true })
      }
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
    // 登录前匿名跑的评审归属还是 "anonymous"，不认领的话登录后所有路由一律
    // 404 ——"登录看完整报告"会变成"报告凭空消失"。失败不阻断登录：报告页
    // 打开时还会再试一次（见 ReportPage）。
    await claimPendingReviews().catch(() => {})
    const identity = await api.me()
    set({ identity, sessionExpired: false })
    // key/用量都换了归属，一起刷新（用量失败不阻断登录）
    await Promise.allSettled([get().refreshKeys(), get().refreshUsage()])
  },

  register: async (email, password, displayName) => {
    const { token } = await api.register(email, password, displayName)
    setToken(token)
    await claimPendingReviews().catch(() => {})
    const identity = await api.me()
    set({ identity, sessionExpired: false })
    await Promise.allSettled([get().refreshKeys(), get().refreshUsage()])
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
