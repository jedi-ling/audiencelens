import { create } from 'zustand'
import type { Review, ReviewListItem, Example, ReviewModeConfig, TaskTypeDetail, SkillType } from '@/lib/mock-data'
import { fetchReviews, fetchReview, deleteReview, fetchExamples, fetchReviewModes, fetchTaskTypes } from '@/lib/api'
import { api } from '@/lib/apiClient'
import type { PersonaPack, ReviewMode, TaskType } from '@/lib/types'

interface ReviewState {
  reviews: ReviewListItem[]
  currentReview: Review | null
  examples: Example[]
  reviewModes: ReviewModeConfig[]
  taskTypes: TaskTypeDetail[]
  loading: boolean
  setReviews: (reviews: ReviewListItem[]) => void
  setCurrentReview: (review: Review | null) => void
  setLoading: (loading: boolean) => void
  initReviews: () => Promise<void>
  fetchReviewById: (id: string) => Promise<Review | null>
  /** 走 v2 异步链路创建评审，成功返回 review_id；失败向上抛（页面负责展示错误）。
   *  此前走 v1 同步接口：阻塞 FastAPI 线程池、无视 BYOK key、无 key 时模拟数据入库。 */
  createNewReview: (data: {
    task_type: string
    artifact_bundle: Record<string, unknown>
    /** 必填，且必须是 selected_personas 真正所属的那个包。
     *  以前这里是可选的、下面还有个 `?? 'game-core'` 兜底：Wizard 未选包时
     *  允许跨包挑人，提交时却被兜底成 game-core，后端
     *  PersonaService.select_panel_by_mode 只在该包内按 id 过滤，
     *  用户选的 VR / 无障碍等人格被整包丢弃且零提示。兜底删掉后，
     *  "选了谁"与"跑了谁"必须由调用方保证一致。 */
    persona_pack: string
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
  /** 拉全部评审。fetchReviews() 现在内部翻页翻到底（此前它不传 offset/limit，
   *  只拿得到后端默认的最近 20 条，第 21 条以后的评审在界面上等于消失）。
   *  需要"分页 + 加载更多"的界面请直接用 fetchReviewsPage()，别用这个。 */
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
      // 不再兜底成 'game-core'：那个兜底正是"用户选的人格被静默丢弃"的成因。
      persona_pack: data.persona_pack as PersonaPack,
      selected_personas: data.selected_personas?.length ? data.selected_personas : undefined,
      skill_type: data.skill_type ?? null,
      enable_evaluation: data.enable_evaluation ?? false,
      enable_red_team: data.enable_red_team ?? false,
    })
    return res.review_id
  },
  /** 删除失败要往上抛：以前这里 catch {} 吞掉异常，界面上表现为"点了删除，
   *  没报错也没消失"——用户只能反复点。调用方负责把 message 显示出来。 */
  deleteReviewById: async (id: string) => {
    await deleteReview(id)
    set((state) => ({ reviews: state.reviews.filter((r) => r.id !== id) }))
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
