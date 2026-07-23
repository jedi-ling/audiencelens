import { create } from 'zustand'
import type { Review, Example, ReviewModeConfig, TaskTypeDetail, SkillType } from '@/lib/mock-data'
import { fetchReviews, fetchReview, deleteReview, fetchExamples, fetchReviewModes, fetchTaskTypes } from '@/lib/api'
import { api } from '@/lib/apiClient'
import type { PersonaPack, ReviewMode, TaskType } from '@/lib/types'

interface ReviewState {
  reviews: Review[]
  currentReview: Review | null
  examples: Example[]
  reviewModes: ReviewModeConfig[]
  taskTypes: TaskTypeDetail[]
  loading: boolean
  setReviews: (reviews: Review[]) => void
  setCurrentReview: (review: Review | null) => void
  setLoading: (loading: boolean) => void
  initReviews: () => Promise<void>
  fetchReviewById: (id: string) => Promise<Review | null>
  /** 走 v2 异步链路创建评审，成功返回 review_id；失败向上抛（页面负责展示错误）。
   *  此前走 v1 同步接口：阻塞 FastAPI 线程池、无视 BYOK key、无 key 时模拟数据入库。 */
  createNewReview: (data: {
    task_type: string
    artifact_bundle: Record<string, unknown>
    persona_pack?: string
    selected_personas?: string[]
    mode?: string
    skill_type?: SkillType
    enable_evaluation?: boolean
    enable_red_team?: boolean
  }) => Promise<string>
  deleteReviewById: (id: string) => Promise<void>
  fetchExamplesList: () => Promise<void>
  fetchReviewModesList: () => Promise<void>
  fetchTaskTypesList: () => Promise<void>
}

export const useReviewStore = create<ReviewState>((set) => ({
  reviews: [],
  currentReview: null,
  examples: [],
  reviewModes: [],
  taskTypes: [],
  loading: false,
  setReviews: (reviews) => set({ reviews }),
  setCurrentReview: (currentReview) => set({ currentReview }),
  setLoading: (loading) => set({ loading }),
  initReviews: async () => {
    set({ loading: true })
    try {
      const reviews = await fetchReviews()
      set({ reviews, loading: false })
    } catch {
      set({ loading: false })
    }
  },
  fetchReviewById: async (id: string) => {
    try {
      const review = await fetchReview(id)
      set({ currentReview: review })
      return review
    } catch {
      return null
    }
  },
  createNewReview: async (data) => {
    // Wizard 的材料是 {type: 字段名, description: 内容} 形态——v2 引擎
    // （run_panel/render_prompt/precheck）原生就按这个形态读，无需转换
    const res = await api.createReview({
      task_type: data.task_type as TaskType,
      artifact: {
        title: (data.artifact_bundle.title as string) ?? '',
        materials: (data.artifact_bundle.materials ?? []) as Array<{ type: string; description: string }>,
      },
      mode: (data.mode ?? 'standard') as ReviewMode,
      persona_pack: (data.persona_pack ?? 'game-core') as PersonaPack,
      selected_personas: data.selected_personas?.length ? data.selected_personas : undefined,
      skill_type: data.skill_type ?? null,
      enable_evaluation: data.enable_evaluation ?? false,
      enable_red_team: data.enable_red_team ?? false,
    })
    return res.review_id
  },
  deleteReviewById: async (id: string) => {
    try {
      await deleteReview(id)
      set((state) => ({ reviews: state.reviews.filter((r) => r.id !== id) }))
    } catch {}
  },
  fetchExamplesList: async () => {
    try {
      const examples = await fetchExamples()
      set({ examples })
    } catch {}
  },
  fetchReviewModesList: async () => {
    try {
      const reviewModes = await fetchReviewModes()
      set({ reviewModes })
    } catch {}
  },
  fetchTaskTypesList: async () => {
    try {
      const taskTypes = await fetchTaskTypes()
      set({ taskTypes })
    } catch {}
  },
}))
