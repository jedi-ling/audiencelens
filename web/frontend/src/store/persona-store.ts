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
  setPersonas: (personas: Persona[]) => void
  setPacks: (packs: PersonaPack[]) => void
  setSelectedPack: (packId: string | null) => void
  setCompareIds: (ids: [string, string] | null) => void
  setSearchQuery: (query: string) => void
  initPersonas: () => Promise<void>
}

export const usePersonaStore = create<PersonaState>((set) => ({
  personas: [],
  packs: [],
  selectedPack: null,
  compareIds: null,
  searchQuery: '',
  initialized: false,
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
      set({ personas, packs: localizedPacks, initialized: true })
    } catch {
      set({ initialized: true })
    }
  },
}))
