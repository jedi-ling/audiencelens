/**
 * 任务类型页（TaskTypesPage.tsx）。owner: agent 7。
 *
 * ⚠ 这里只有**页面框架**的文案。清单本身（name_zh / description / stance_enum /
 * score_dimensions / base_dimensions）全部来自后端 /api/task-types，英文事实源是
 * 后端 catalog.en-US.json（契约 D4/D5），前端不许在这里另写一份——
 * 页面刻意不回落到本地 TASK_TYPES，就是为了不让用户把一份可能过期的本地清单
 * 当成后端的真实能力。
 *
 * 分类名（开发阶段/运营阶段/…）是**纯前端概念**：后端 TaskTypeResponse 里没有
 * category 字段。它的中文源在 mock-data.ts 的 TASK_TYPE_CATEGORIES，本文件是
 * 显示层的 key 表。CreateReviewPage 也显示同一批分类名，按契约 D10/§11 各抽各的，
 * 已写进交付报告请 batch-0 裁决要不要收进 catalog.*。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '任务类型',
  'header.title': '任务类型',
  // 副标题三态：拿到清单才显示数字，加载中/失败时不显示任何可被证伪的计数。
  'count.total': '共 {{count}} 种评审任务类型',
  'header.loading': '正在加载任务类型清单',
  'header.error': '任务类型清单加载失败',

  // ---- 清单加载失败 ----
  /** tApiError 的 fallbackKey：不是 ApiError（断网、代码抛了 TypeError）时用它。 */
  'list.error': '加载任务类型失败',
  'list_error.title': '无法加载任务类型',
  'list_error.desc': '{{reason}}——这里显示的不是"没有任务类型"，而是没能取到清单，请重试。',
  'list_error.cta': '重新加载',
  /** 后端真的一个类型都没开放。与"加载失败"必须分得开，所以是两条文案。 */
  'list.empty': '后端当前没有开放任何评审任务类型',

  // ---- 分类筛选 ----
  'filter.tab': '全部',
  'category_development.label': '开发阶段',
  'category_operations.label': '运营阶段',
  'category_community.label': '社区阶段',
  'category_product.label': '通用产品',
  /** 后端返回了本地没登记 category 的新类型时，它归到这一档照常显示。 */
  'category_other.label': '其他',

  // ---- 卡片 ----
  'card_stance.label': '立场：',
  'card_score.label': '评分维度：',
  'card.cta': '点击查看详情 →',

  // ---- 详情弹窗 ----
  'modal.title': '任务类型详情',
  // 括号里的英文是后端字段名，两侧都原样保留：这几行本来就是给要对接口的人看的。
  'modal_id.label': 'ID',
  'modal_name.label': '中文名称',
  'modal_desc.label': '描述',
  'modal_stance.label': '立场枚举 (stance_enum)',
  'modal_score.label': '评分维度 (score_dimensions)',
  'modal_base.label': '基础维度 (base_dimensions)',
  'detail.error': '加载详情失败',
  'detail_error.title': '无法加载详情',
  'detail_error.hint': '请稍后重试',
} satisfies Messages
