import { create } from 'zustand'
import type { Review, ReviewListItem, Example, ReviewModeConfig, TaskTypeDetail, SkillType } from '@/lib/mock-data'
import { fetchReviews, fetchReview, deleteReview, fetchExamples, fetchReviewModes, fetchTaskTypes } from '@/lib/api'
import { api } from '@/lib/apiClient'
import type { PersonaPack, ReviewMode, TaskType } from '@/lib/types'
import { tApiError } from '@/i18n/api-error'

interface ReviewState {
  reviews: ReviewListItem[]
  currentReview: Review | null
  examples: Example[]
  reviewModes: ReviewModeConfig[]
  taskTypes: TaskTypeDetail[]
  loading: boolean
  /** 评审列表加载失败的原因。有它页面才能把"你还没有评审"和"没拉到"分开说，
   *  否则一次 401 或后端没起就长得像"我的评审全没了"。 */
  reviewsError: string | null
  /** 示例列表加载失败的原因。示例区块此前是 `examples.length > 0 &&`：
   *  拉失败就整块消失，用户既看不到入口也不知道它本该存在。 */
  examplesError: string | null
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
    /** 两层评审：全包初筛 → 分歧门禁 → 深评（引擎 wide_screen） */
    wide_screen?: boolean
    /** 自适应面板：按边际价值代理逐个扩面（引擎 adaptive_panel） */
    adaptive_panel?: boolean
  }) => Promise<string>
  /** 后端在免费次数用完时会把高级技能/红队降级，并回一句 skill_degraded 说明。
   *  这句话必须让用户看见：否则他以为红队正常跑了，实际拿到的是普通模式的报告。
   *  createNewReview 的返回值签名保持 string（调用方只关心 review_id），
   *  降级说明放这里，由页面在跳转前读出来展示。每次创建都会覆写（成功且未降级
   *  时置 null），不会把上一次的提示留到下一次。 */
  lastSkillDegraded: string | null
  clearSkillDegraded: () => void
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
  reviewsError: null,
  examplesError: null,
  lastSkillDegraded: null,
  clearSkillDegraded: () => set({ lastSkillDegraded: null }),
  setReviews: (reviews) => set({ reviews }),
  setCurrentReview: (currentReview) => set({ currentReview }),
  setLoading: (loading) => set({ loading }),
  /** 拉全部评审。fetchReviews() 现在内部翻页翻到底（此前它不传 offset/limit，
   *  只拿得到后端默认的最近 20 条，第 21 条以后的评审在界面上等于消失）。
   *  需要"分页 + 加载更多"的界面请直接用 fetchReviewsPage()，别用这个。 */
  initReviews: async () => {
    set({ loading: true, reviewsError: null })
    try {
      const reviews = await fetchReviews()
      set({ reviews, loading: false, reviewsError: null })
    } catch (e) {
      // 不清空 reviews：拉失败时把上一次的列表留着，比当场变成"空空如也"更诚实。
      set({ loading: false, reviewsError: tApiError(e, 'error.store.review_list') })
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
      // 只加类型不加这一行就是"传了但被丢弃"——enable_evaluation /
      // enable_red_team 都真实踩过这个坑（开关从 UI 传到后端被静默吞掉，
      // 用户以为开了、实际没开，且没有任何回执）。
      wide_screen: data.wide_screen ?? false,
      adaptive_panel: data.adaptive_panel ?? false,
    })
    // 显式写 null 而不是"有值才写"：不覆盖的话，上一次降级的提示会挂在
    // store 上，下一次正常创建时被页面当成本次的降级又弹一遍。
    set({ lastSkillDegraded: res.skill_degraded ?? null })
    // 注意：res.guest_token 不在这里处理。首次匿名发起评审时后端会铸造独立游客
    // 身份、把评审落在那个**新的** user_id 下；token 丢了就等于这条评审对它自己
    // 的作者隐身（跳过去的进度页 404、WS 被拒，而次数已经扣掉）。这段收在
    // apiClient.createReview → adoptGuestToken 里，是全站唯一的创建出口，
    // 不要在这里再抄一份——这一页之前正是因为"没抄"而漏掉了整条游客链路。
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
      set({ examples, examplesError: null })
    } catch (e) {
      set({ examplesError: tApiError(e, 'error.store.examples') })
    }
  },
  // 下面两个是 UI 配置项（模式说明、任务类型说明），页面都有静态兜底文案，
  // 拉不到不会让用户误以为"自己的东西没了"，所以不单开 error 字段；
  // 但仍要在控制台留痕，否则线上排查时连"请求失败过"都看不出来。
  fetchReviewModesList: async () => {
    try {
      const reviewModes = await fetchReviewModes()
      set({ reviewModes })
    } catch (e) {
      console.warn('[review-store] 评审模式配置加载失败，页面将使用内置兜底文案', e)
    }
  },
  fetchTaskTypesList: async () => {
    try {
      const taskTypes = await fetchTaskTypes()
      set({ taskTypes })
    } catch (e) {
      console.warn('[review-store] 任务类型配置加载失败，页面将使用内置兜底文案', e)
    }
  },
}))
