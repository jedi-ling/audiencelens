import { create } from 'zustand'
import type { Persona, PersonaPack } from '@/lib/mock-data'
import { fetchPersonas, fetchPersonaPacks } from '@/lib/api'
import { tApiError } from '@/i18n/api-error'
import { t, missingMarker } from '@/i18n/runtime'
import { getLocale } from '@/i18n/locale'
import type { PlainMessageKey } from '@/i18n/keys.gen'

/** 同 i18n/api-error.ts：这里只喂无插值的 key，收窄签名免得每处都写空对象。 */
const tPlain = t as unknown as (key: PlainMessageKey) => string

/**
 * 人格包展示名的 overlay：后端 packs 端点回的 name 在这里被覆盖掉。
 * 契约 D5 的表里 PACK_NAME_MAP 的 zh / en 事实源**都是前端**，所以这是唯一事实源，
 * 不是离线兜底。译文在 i18n/locales/{zh,en}/catalog.persona_pack.ts。
 *
 * 存的是 **key 不是文案**：这张表在模块求值时就固定了，存翻译结果的话切换语言
 * 不会重新求值，包名会一直停在打开页面时的那种语言。
 */
const PACK_NAME_KEY: Record<string, PlainMessageKey> = {
  'game-core': 'catalog.persona_pack.game_core',
  'accessibility': 'catalog.persona_pack.accessibility',
  'mobile-f2p': 'catalog.persona_pack.mobile_f2p',
  'vr-immersive': 'catalog.persona_pack.vr_immersive',
  'competitive-esport': 'catalog.persona_pack.competitive_esport',
  'educational-serious': 'catalog.persona_pack.educational_serious',
  'family-casual': 'catalog.persona_pack.family_casual',
  'indie-creative': 'catalog.persona_pack.indie_creative',
  'general-consumer': 'catalog.persona_pack.general_consumer',
  'startup-panel': 'catalog.persona_pack.startup_panel',
  // 集成阶段（跑完 `npm run i18n:gen`，keys.gen.ts 里已有这条 key）补上。
  // 并发期它被注释掉的原因见 git 历史：那时 keys.gen.ts 还是旧的，写进来 tsc 会当场红。
  // 补之前角色库那一栏漏出的是 ⟦missing:catalog.persona_pack.launch_compliance⟧
  // ——被看见、没有静默回落成中文，卡口的行为是对的。
  'launch-compliance': 'catalog.persona_pack.launch_compliance',
}

/**
 * 后端 panel_id → 展示名。
 *
 * 查不到时**不回落成后端的 pack.name**（原先是 `?? pack.name`）：后端那份是中文，
 * 在英文界面上就是"混中文且没人发现"，正是契约 D8 点名禁止的形态
 * （同一条规则修的还有 PersonaRadarChart 的 `?? d.axis`）。
 * 显式标出缺译的代价是中文界面上也会看到 ⟦missing:…⟧——那正是目的：
 * 后端新增了一个包而前端没跟上，这件事必须有人看得见。
 *
 * export 是 batch-2 接线时加的：PersonasPage 三处（侧栏包名、抽屉包名、卡片上的
 * 所属包）此前直接渲染后端回的 pack.name（中文），要接上这份 overlay 就得用这个函数。
 * 在页面里另写一份 panel_id → key 的映射等于给同一批包名立第二个 owner，
 * 正是契约 D5 要防的"同一个包在两个页面显示两个名字"。
 */
export function packName(panelId: string): string {
  const key = PACK_NAME_KEY[panelId]
  if (!key) {
    // 包 id 走第二个实参而不是拼进模板串：i18n-scan 只豁免 console 调用的
    // 第一个字面量实参，模板串它认不出来，会把这行开发者日志报成"待外化文案"。
    console.error('[persona-store] 未知人格包，PACK_NAME_KEY 与 catalog.persona_pack 需要补一条：', panelId)
    return missingMarker(`catalog.persona_pack.${panelId.replace(/-/g, '_')}`, getLocale())
  }
  return tPlain(key)
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
      // 已知限制（与 i18n/locales/zh/error.store.ts 记的是同一类）：包名在这里
      // 被翻成字符串存进 store，用户此后切换界面语言，列表里的包名不会跟着变，
      // 要等下一次 initPersonas。要根治得让 store 只存 panel_id、由页面渲染时翻，
      // 那会改动 store 的公开形状（PersonaPack.name），波及消费它的页面文件。
      // 本期不做，记在交付报告里。
      const localizedPacks = packs.map((pack) => ({
        ...pack,
        name: packName(pack.panel_id),
      }))
      set({ personas, packs: localizedPacks, initialized: true, error: null })
    } catch (e) {
      // 只记错误，不动 personas/packs：上一次成功拉到的角色还留在界面上比
      // 突然清空更接近事实。initialized 仍置 true 是为了让页面退出 loading 态，
      // 由 error 字段接管展示。
      set({
        initialized: true,
        // 走 tApiError：后端 message 更具体，但只在语种对得上时才用；
        // 非 ApiError（网络层的 TypeError）不再把 "Failed to fetch" 甩给用户。
        error: tApiError(e, 'error.store.personas'),
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
