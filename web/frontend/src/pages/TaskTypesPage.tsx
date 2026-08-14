import { useState, useEffect, useCallback, useMemo } from 'react'
import { cn } from '@/lib/utils'
import { TASK_TYPES, TASK_TYPE_CATEGORIES } from '@/lib/mock-data'
import type { TaskTypeDetail } from '@/lib/mock-data'
import { fetchTaskTypes, fetchTaskType } from '@/lib/api'
import { X, Loader2, AlertTriangle, Shapes } from 'lucide-react'
import { PageShell, PageHeader, EmptyState, CARD_GRID_CLASS, SECONDARY_BUTTON_CLASS } from '@/components/ui'
import { t, missingMarker } from '@/i18n/runtime'
import { localizeBackendTaskType, localizeStanceLabels } from '@/i18n/catalog'
import { getLocale } from '@/i18n/locale'
import { useDocumentTitle } from '@/i18n/head'
import { tApiError, tApiErrorParts } from '@/i18n/api-error'
import type { PlainMessageKey } from '@/i18n/keys.gen'

// category 是纯前端概念：后端 TaskTypeResponse 里没有这个字段，只有 task_type/name_zh/
// description/stance_enum/score_dimensions/base_dimensions。所以分组只能靠本地的
// id -> category 映射。这里的取舍是：本地映射只用来**分组和补图标**，绝不用来决定
// "有哪些类型"。后端新增一个本地没登记的类型时，它落进"其他"照常显示；如果反过来让
// 本地表当白名单，新类型会被静默过滤掉，用户在界面上永远看不到后端已经支持的能力，
// 而且没有任何报错提示这件事发生过。
const OTHER_CATEGORY = 'other'

// 本地 TASK_TYPES 仅作展示补充（图标、分类），不参与"存在性"判断。
const localById = new Map(TASK_TYPES.map((tt) => [tt.id, tt]))

/**
 * 分类名的 key 表。分类是纯前端概念（见文件头），中文源在 mock-data 的
 * TASK_TYPE_CATEGORIES，这里是显示层。
 *
 * 存的是 **key 不是文案**：模块级常量在求值时就固定了，存翻译结果的话切换语言
 * 不会重新求值，分类按钮会一直停在打开页面时的那种语言。
 * 也刻意不从 TASK_TYPE_CATEGORIES 拼 key——拼出来的 key 只有运行时才知道存不存在，
 * 写成显式表的话，mock-data 加了一类而这里没跟上是编译错误。
 */
const CATEGORY_LABEL_KEYS: Record<string, PlainMessageKey> = {
  development: 'page.task_types.category_development.label',
  operations: 'page.task_types.category_operations.label',
  community: 'page.task_types.category_community.label',
  product: 'page.task_types.category_product.label',
  [OTHER_CATEGORY]: 'page.task_types.category_other.label',
}

/** 查不到不回落成 id、也不回落成"其他"：那会把一条缺译伪装成一个正常的分类名（契约 D8）。 */
function categoryLabel(id: string): string {
  const key = CATEGORY_LABEL_KEYS[id]
  return key ? t(key) : missingMarker(`page.task_types.category_${id}.label`, getLocale())
}

const categoryIcons = new Map(TASK_TYPE_CATEGORIES.map((c) => [c.id, c.icon]))

export default function TaskTypesPage() {
  // useDocumentTitle 内部 useLocale()，本页借它一并订阅 ui_lang：
  // t() 是普通函数、不带响应性，切语言时必须有人触发重渲染。
  useDocumentTitle('page.task_types.meta.title')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [taskTypes, setTaskTypes] = useState<TaskTypeDetail[] | null>(null)
  // 存的是**错误对象本身**，不是翻好的字符串：翻译在渲染期做，切语言时这条报错
  // 才会跟着变。存字符串的话，报错会一直停在出错那一刻的语言。
  const [listError, setListError] = useState<unknown>(null)
  const [selectedDetail, setSelectedDetail] = useState<TaskTypeDetail | null>(null)
  const [detailError, setDetailError] = useState<unknown>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [showModal, setShowModal] = useState(false)

  const loadList = useCallback(() => {
    setListError(null)
    setTaskTypes(null)
    fetchTaskTypes()
      .then((data) => setTaskTypes(data))
      // 失败时绝不回落到本地 TASK_TYPES：那会让用户看到一份可能已经过期的清单，
      // 却以为加载成功了。"空"和"加载失败"必须能分辨。
      .catch((err: unknown) => setListError(err))
  }, [])

  useEffect(() => {
    loadList()
  }, [loadList])

  const categoryOf = useCallback((taskTypeId: string) => {
    const local = localById.get(taskTypeId)
    // 本地登记的 category 也可能写了个 TASK_TYPE_CATEGORIES 里不存在的值，
    // 那种情况同样归入"其他"，否则这张卡片会属于一个渲染不出来的分类按钮。
    if (local && CATEGORY_LABEL_KEYS[local.category]) return local.category
    return OTHER_CATEGORY
  }, [])

  // 所有计数都对后端返回的数组现算，本地数组长度只代表本地表有多少条，与真实能力无关。
  const categoryTabs = useMemo(() => {
    if (!taskTypes) return []
    const counts = new Map<string, number>()
    for (const tt of taskTypes) {
      const cat = categoryOf(tt.task_type)
      counts.set(cat, (counts.get(cat) ?? 0) + 1)
    }
    // 只渲染真有类型的分类：后端删光某类之后留一个"0"的按钮点进去是空页，没意义。
    // 这里只算 id 与计数，**不算分类名**：memo 的依赖里没有 ui_lang，
    // 把译文缓存进来的话，切语言后按钮上的名字不会更新。名字在渲染处才 t()。
    return [...TASK_TYPE_CATEGORIES.map((c) => c.id), OTHER_CATEGORY]
      .filter((id) => (counts.get(id) ?? 0) > 0)
      .map((id) => ({ id, count: counts.get(id) ?? 0 }))
  }, [taskTypes, categoryOf])

  const visibleTypes = useMemo(() => {
    if (!taskTypes) return []
    if (selectedCategory === 'all') return taskTypes
    // 选中的分类可能在重新加载后不复存在（后端删空了那一类），此时按钮已经不渲染，
    // 再按它过滤会得到一个没有任何按钮处于选中态的空白页，用户会以为数据丢了。
    if (!categoryTabs.some((c) => c.id === selectedCategory)) return taskTypes
    return taskTypes.filter((tt) => categoryOf(tt.task_type) === selectedCategory)
  }, [taskTypes, selectedCategory, categoryOf, categoryTabs])

  const handleCardClick = async (taskType: string) => {
    setLoadingDetail(true)
    setDetailError(null)
    setSelectedDetail(null)
    setShowModal(true)
    try {
      const detail = await fetchTaskType(taskType)
      setSelectedDetail(detail)
    } catch (err) {
      // 这里原来会用本地数据拼一个详情，并把 base_dimensions 写死成 ['clarity','trust']。
      // base_dimensions 前端根本无从得知，编出来的值会被用户当成事实。宁可报错。
      setDetailError(err)
    } finally {
      setLoadingDetail(false)
    }
  }

  const closeModal = () => {
    setShowModal(false)
    setSelectedDetail(null)
    setDetailError(null)
  }

  const tabClass = (active: boolean) =>
    cn(
      'flex items-center gap-2 px-4 py-2 rounded-lg font-display font-medium text-sm whitespace-nowrap transition-all duration-200',
      active
        ? 'bg-brand-primary/10 text-brand-primary border border-brand-primary/30'
        : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
    )

  const badgeClass = (active: boolean) =>
    cn(
      'px-1.5 py-0.5 rounded text-xs font-mono',
      active ? 'bg-brand-primary/20 text-brand-primary' : 'bg-bg-secondary/50 text-text-muted'
    )

  // 后端原文（语种可能与界面不一致）单独拿出来，渲染时放进 title 属性，
  // 不与主文案并排显示：英文界面上并排一句中文，用户会以为界面坏了。见契约 D2 / 5.6。
  const detailErrorParts =
    detailError !== null ? tApiErrorParts(detailError, 'page.task_types.detail.error') : null

  return (
    <PageShell size="grid">
      <PageHeader
        title={t('page.task_types.header.title')}
        // 数字只在真拿到后端列表时才出现，加载中/失败时不显示任何可被证伪的计数
        subtitle={
          taskTypes
            ? t('page.task_types.count.total', { count: taskTypes.length })
            : listError !== null
              ? t('page.task_types.header.error')
              : t('page.task_types.header.loading')
        }
      />

      {listError !== null && (
        <EmptyState
          icon={AlertTriangle}
          tone="error"
          title={t('page.task_types.list_error.title')}
          // EmptyState 的 description 只收字符串，接不住 tApiErrorParts 的 detail
          // （后端中文原文）。这条已写进交付报告，等 batch-0 决定共享组件怎么放它。
          description={t('page.task_types.list_error.desc', {
            reason: tApiError(listError, 'page.task_types.list.error'),
          })}
          action={
            <button onClick={loadList} className={SECONDARY_BUTTON_CLASS}>
              {t('page.task_types.list_error.cta')}
            </button>
          }
        />
      )}

      {!taskTypes && listError === null && (
        <div className="py-16 text-center">
          <Loader2 className="w-6 h-6 text-cyan animate-spin mx-auto mb-3" strokeWidth={1.25} />
          <p className="text-sm text-text-secondary">{t('common.ui.loading')}</p>
        </div>
      )}

      {taskTypes && taskTypes.length === 0 && (
        <EmptyState icon={Shapes} title={t('page.task_types.list.empty')} />
      )}

      {taskTypes && taskTypes.length > 0 && (
        <>
          <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2 scrollbar-hide -mx-4 px-4">
            <button onClick={() => setSelectedCategory('all')} className={tabClass(selectedCategory === 'all')}>
              <span>{t('page.task_types.filter.tab')}</span>
              <span className={badgeClass(selectedCategory === 'all')}>{taskTypes.length}</span>
            </button>

            {categoryTabs.map((category) => {
              const Icon = categoryIcons.get(category.id) ?? Shapes
              const active = selectedCategory === category.id
              return (
                <button key={category.id} onClick={() => setSelectedCategory(category.id)} className={tabClass(active)}>
                  <Icon className="w-4 h-4" strokeWidth={1.25} />
                  <span>{categoryLabel(category.id)}</span>
                  <span className={badgeClass(active)}>{category.count}</span>
                </button>
              )
            })}
          </div>

          {/* 网格断点与角色库/技能中心统一一档（sm 2 列 / lg 3 列），
              卡片内容差异大，靠 line-clamp + mt-auto 拉齐标题/描述/底部基线 */}
          <div className={CARD_GRID_CLASS}>
            {visibleTypes.map((tt) => {
              const local = localById.get(tt.task_type)
              const categoryId = categoryOf(tt.task_type)
              // 后端新类型本地没有图标，用通用图标兜底，不能因为缺图标就不渲染。
              const Icon = local?.IconComponent ?? Shapes
              const CategoryIcon = categoryIcons.get(categoryId) ?? Shapes
              // 名称/描述按 ui_lang 取：后端今天只回中文（catalog_en.py 已就位但端点
              // 还没引用它），英文界面直接渲染 name_zh 就是"看不出是缺译的中文"。
              // zh 仍用后端原文——后端才是中文事实源，新类型也照常显示。见 i18n/catalog.ts §B2。
              const text = localizeBackendTaskType(tt)

              return (
                <button
                  key={tt.task_type}
                  onClick={() => handleCardClick(tt.task_type)}
                  className="flex h-full flex-col gap-3 p-5 rounded-xl border border-border bg-bg-card hover:bg-bg-card-hover hover:border-brand-primary/30 transition-all text-left group"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-brand-primary/10 shrink-0">
                      <Icon className="w-5 h-5 text-brand-primary" strokeWidth={1.25} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-sm text-text-primary group-hover:text-brand-primary transition-colors truncate">
                        {text.name}
                      </h3>
                      <div className="flex items-center gap-1 text-xs text-text-muted">
                        <CategoryIcon className="w-3 h-3" strokeWidth={1.25} />
                        <span>{categoryLabel(categoryId)}</span>
                      </div>
                    </div>
                  </div>

                  {/* 描述行数差很多：clamp 到 3 行才能让同一行网格的卡片底边对齐 */}
                  <p className="text-xs text-text-secondary leading-relaxed line-clamp-3">{text.description}</p>

                  {/* stance_enum 的值是 wire contract（引擎的聚类键，后端 parity 测试逐字
                      保护），永不翻译。英文显示标签的下发通道是后端的 stance_labels_en
                      （契约 D4，见 locales/zh/enum.primary_stance.ts 的文件头）。
                      端点现在已经在发它了（catalog_en.py 已接线），所以这里改走
                      localizeStanceLabels()：value 恒是 wire 值、label 才是画上去的字。
                      前端仍然不许在这里另造一份标签——理由同上，那会立第二个 owner。 */}
                  {tt.stance_enum.length > 0 && (
                    <div>
                      <span className="text-xs text-text-muted">{t('page.task_types.card_stance.label')}</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {localizeStanceLabels(tt).map((s) => (
                          <span key={s.value} className="px-1.5 py-0.5 rounded text-[10px] bg-cyan/10 text-cyan">
                            {s.label}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {tt.score_dimensions.length > 0 && (
                    <div>
                      <span className="text-xs text-text-muted">{t('page.task_types.card_score.label')}</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {tt.score_dimensions.map((d) => (
                          <span key={d} className="px-1.5 py-0.5 rounded text-[10px] bg-text-muted/10 text-text-secondary">
                            {d}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="text-xs text-brand-primary/60 group-hover:text-brand-primary transition-colors mt-auto pt-1">
                    {t('page.task_types.card.cta')}
                  </div>
                </button>
              )
            })}
          </div>
        </>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/25 backdrop-blur-sm" onClick={closeModal} />
          <div className="relative w-full max-w-lg rounded-2xl border border-border bg-bg-primary shadow-2xl animate-fade-in overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-border">
              <h2 className="text-lg font-semibold text-text-primary">{t('page.task_types.modal.title')}</h2>
              <button
                onClick={closeModal}
                className="p-1.5 rounded-lg hover:bg-bg-card text-text-muted hover:text-text-primary transition-colors"
              >
                <X className="w-5 h-5" strokeWidth={1.25} />
              </button>
            </div>
            <div className="p-5 max-h-[70vh] overflow-y-auto">
              {loadingDetail ? (
                <div className="py-8 text-center">
                  <Loader2 className="w-6 h-6 text-cyan animate-spin mx-auto mb-3" strokeWidth={1.25} />
                  <p className="text-sm text-text-secondary">{t('common.ui.loading')}</p>
                </div>
              ) : selectedDetail ? (
                (() => {
                // 与卡片同一个读取器，免得同一个任务类型在卡片上是英文、点开是中文。
                const detailText = localizeBackendTaskType(selectedDetail)
                return (
                <div className="space-y-4">
                  <div>
                    <span className="text-xs text-text-muted">{t('page.task_types.modal_id.label')}</span>
                    <p className="text-sm font-mono text-text-primary mt-0.5">{selectedDetail.task_type}</p>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">{t('page.task_types.modal_name.label')}</span>
                    <p className="text-sm text-text-primary mt-0.5">{detailText.name}</p>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">{t('page.task_types.modal_desc.label')}</span>
                    <p className="text-sm text-text-secondary mt-0.5">{detailText.description}</p>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">{t('page.task_types.modal_stance.label')}</span>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {localizeStanceLabels(selectedDetail).map((s) => (
                        <span key={s.value} className="px-2 py-1 rounded-md text-xs bg-cyan/10 text-cyan border border-cyan/20">
                          {s.label}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">{t('page.task_types.modal_score.label')}</span>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {selectedDetail.score_dimensions.map((d) => (
                        <span key={d} className="px-2 py-1 rounded-md text-xs bg-text-muted/10 text-text-secondary border border-black/5">
                          {d}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">{t('page.task_types.modal_base.label')}</span>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {selectedDetail.base_dimensions.map((d) => (
                        <span key={d} className="px-2 py-1 rounded-md text-xs bg-brand-primary/10 text-brand-primary border border-brand-primary/20">
                          {d}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                )
                })()
              ) : (
                <div className="py-6 text-center">
                  <AlertTriangle className="w-6 h-6 text-severity-critical mx-auto mb-3" strokeWidth={1.25} />
                  <p className="text-sm text-text-primary">{t('page.task_types.detail_error.title')}</p>
                  {detailErrorParts ? (
                    <p className="text-xs text-text-secondary mt-1" title={detailErrorParts.detail}>
                      {detailErrorParts.text}
                    </p>
                  ) : (
                    <p className="text-xs text-text-secondary mt-1">{t('page.task_types.detail_error.hint')}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </PageShell>
  )
}
