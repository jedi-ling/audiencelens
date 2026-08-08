import { create } from 'zustand'
import type { Persona, PersonaPack } from '@/lib/mock-data'
import { fetchPersonas, fetchPersonaPacks } from '@/lib/api'

const PACK_NAME_MAP: Record<string, string> = {
  'game-core': '核心玩家',
  'accessibility': '无障碍倡导',
  'mobile-f2p': '移动免费',
  'vr-immersive': 'VR沉浸',
  'competitive-esport': '竞技选手',
  'educational-serious': '教育严肃',
  'family-casual': '休闲家庭',
  'indie-creative': '独立创意',
  'general-consumer': '通用消费者',
  'startup-panel': '创业评审团',
}

interface PersonaState {
  personas: Persona[]
  packs: PersonaPack[]
  selectedPack: string | null
  compareIds: [string, string] | null
  searchQuery: string
  initialized: boolean
  /** 加载失败的原因。null 表示"这次真的加载成功了"，非 null 表示 personas/packs
   *  里的空数组是失败的残留、不是真实结果。
   *  不区分这两者的话，网络抖动 / 401 / 后端没起，在页面上和"这个包里一个角色
   *  都没有"长得一模一样，用户会以为自己的角色包空了而不是重试。 */
  error: string | null
  setPersonas: (personas: Persona[]) => void
  setPacks: (packs: PersonaPack[]) => void
  setSelectedPack: (packId: string | null) => void
  setCompareIds: (ids: [string, string] | null) => void
  setSearchQuery: (query: string) => void
  initPersonas: () => Promise<void>
  /** 给失败态的"重新加载"按钮用。initPersonas 被页面写成
   *  `if (!initialized) initPersonas()`，失败后 initialized 仍是 true
   *  （否则 effect 会跟着 re-render 无限重试），所以重试必须走这个显式入口。 */
  retryPersonas: () => Promise<void>
}

export const usePersonaStore = create<PersonaState>((set, get) => ({
  personas: [],
  packs: [],
  selectedPack: null,
  compareIds: null,
  searchQuery: '',
  initialized: false,
  error: null,
  setPersonas: (personas) => set({ personas }),
  setPacks: (packs) => set({ packs }),
  setSelectedPack: (selectedPack) => set({ selectedPack }),
  setCompareIds: (compareIds) => set({ compareIds }),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  initPersonas: async () => {
    try {
      const [personas, packs] = await Promise.all([fetchPersonas(), fetchPersonaPacks()])
      const localizedPacks = packs.map((pack) => ({
        ...pack,
        name: PACK_NAME_MAP[pack.panel_id] ?? pack.name,
      }))
      set({ personas, packs: localizedPacks, initialized: true, error: null })
    } catch (e) {
      // 只记错误，不动 personas/packs：上一次成功拉到的角色还留在界面上比
      // 突然清空更接近事实。initialized 仍置 true 是为了让页面退出 loading 态，
      // 由 error 字段接管展示。
      set({
        initialized: true,
        error: e instanceof Error ? e.message : '角色列表加载失败',
      })
    }
  },
  retryPersonas: async () => {
    // 不把 initialized 改回 false：页面的 effect 依赖 initialized，
    // 改回去会让 effect 也触发一次 initPersonas，变成一次点击两次请求。
    set({ error: null })
    await get().initPersonas()
  },
}))
