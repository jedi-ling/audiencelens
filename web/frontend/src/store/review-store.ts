import { create } from 'zustand'
import type { Review, Example, ReviewModeConfig, TaskTypeDetail, SkillType } from '@/lib/mock-data'
import { fetchReviews, fetchReview, createReview, deleteReview, fetchExamples, fetchReviewModes, fetchTaskTypes } from '@/lib/api'

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
  createNewReview: (data: {
    task_type: string
    artifact_bundle: Record<string, unknown>
    persona_pack?: string
    selected_personas?: string[]
    mode?: string
    skill_type?: SkillType
    enable_evaluation?: boolean
    enable_red_team?: boolean
  }) => Promise<Review | null>
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
    try {
      const review = await createReview(data)
      set((state) => ({ reviews: [review, ...state.reviews] }))
      return review
    } catch {
      return null
    }
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
