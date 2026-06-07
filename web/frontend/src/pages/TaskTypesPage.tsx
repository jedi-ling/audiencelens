import { useState, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { TASK_TYPES, TASK_TYPE_CATEGORIES } from '@/lib/mock-data'
import type { TaskTypeDetail } from '@/lib/mock-data'
import { fetchTaskTypes, fetchTaskType } from '@/lib/api'
import { X, Loader2, FolderOpen, TrendingUp, Users } from 'lucide-react'

const categoryIcons: Record<string, React.ComponentType<{ className?: string; strokeWidth?: number }>> = {
  development: FolderOpen,
  operations: TrendingUp,
  community: Users,
}

export default function TaskTypesPage() {
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [apiTaskTypes, setApiTaskTypes] = useState<TaskTypeDetail[] | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<TaskTypeDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    fetchTaskTypes()
      .then((data) => setApiTaskTypes(data))
      .catch(() => setApiTaskTypes(null))
  }, [])

  const handleCardClick = async (taskType: string) => {
    setLoadingDetail(true)
    setShowModal(true)
    try {
      const detail = await fetchTaskType(taskType)
      setSelectedDetail(detail)
    } catch {
      const local = TASK_TYPES.find((t) => t.id === taskType)
      if (local) {
        setSelectedDetail({
          task_type: local.id,
          name_zh: local.name,
          description: local.description,
          stance_enum: local.stance_enum ?? [],
          score_dimensions: local.score_dimensions ?? [],
          base_dimensions: ['clarity', 'trust'],
        })
      }
    } finally {
      setLoadingDetail(false)
    }
  }

  const closeModal = () => {
    setShowModal(false)
    setSelectedDetail(null)
  }

  const getApiDetail = (taskTypeId: string): TaskTypeDetail | undefined => {
    return apiTaskTypes?.find((t) => t.task_type === taskTypeId)
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 animate-fade-in">
      <div className="mb-8">
        <h1 className="text-2xl md:text-3xl font-bold text-text-primary font-display mb-2">任务类型</h1>
        <p className="text-text-secondary text-sm">共 {TASK_TYPES.length} 种评审任务类型，覆盖开发、运营、社区全流程</p>
      </div>

      <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2 scrollbar-hide -mx-4 px-4">
        <button
          onClick={() => setSelectedCategory('all')}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg font-display font-medium text-sm whitespace-nowrap transition-all duration-200',
            selectedCategory === 'all'
              ? 'bg-neon-green/10 text-neon-green border border-neon-green/30'
              : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
          )}
        >
          <span>全部</span>
          <span className={cn(
            'px-1.5 py-0.5 rounded text-xs font-mono',
            selectedCategory === 'all' ? 'bg-neon-green/20 text-neon-green' : 'bg-bg-secondary/50 text-text-muted'
          )}>
            {TASK_TYPES.length}
          </span>
        </button>

        {TASK_TYPE_CATEGORIES.map((category) => {
          const Icon = category.icon
          const count = TASK_TYPES.filter((tt) => tt.category === category.id).length
          return (
            <button
              key={category.id}
              onClick={() => setSelectedCategory(category.id)}
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg font-display font-medium text-sm whitespace-nowrap transition-all duration-200',
                selectedCategory === category.id
                  ? 'bg-neon-green/10 text-neon-green border border-neon-green/30'
                  : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
              )}
            >
              <Icon className="w-4 h-4" strokeWidth={1.25} />
              <span>{category.name}</span>
              <span className={cn(
                'px-1.5 py-0.5 rounded text-xs font-mono',
                selectedCategory === category.id ? 'bg-neon-green/20 text-neon-green' : 'bg-bg-secondary/50 text-text-muted'
              )}>
                {count}
              </span>
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {TASK_TYPES
          .filter((tt) => selectedCategory === 'all' || tt.category === selectedCategory)
          .map((tt) => {
            const apiDetail = getApiDetail(tt.id)
            const Icon = tt.IconComponent
            const CategoryIcon = categoryIcons[tt.category]
            const stanceEnum = apiDetail?.stance_enum ?? tt.stance_enum ?? []
            const scoreDimensions = apiDetail?.score_dimensions ?? tt.score_dimensions ?? []

            return (
              <button
                key={tt.id}
                onClick={() => handleCardClick(tt.id)}
                className="flex flex-col gap-3 p-5 rounded-xl border border-border bg-bg-card hover:bg-bg-card-hover hover:border-neon-green/30 transition-all text-left group"
              >
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 flex items-center justify-center rounded-lg bg-neon-green/10 shrink-0">
                    <Icon className="w-5 h-5 text-neon-green" strokeWidth={1.25} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm text-text-primary group-hover:text-neon-green transition-colors truncate">
                      {apiDetail?.name_zh ?? tt.name}
                    </h3>
                    <div className="flex items-center gap-1 text-xs text-text-muted">
                      {CategoryIcon && <CategoryIcon className="w-3 h-3" strokeWidth={1.25} />}
                      <span>{TASK_TYPE_CATEGORIES.find((c) => c.id === tt.category)?.name}</span>
                    </div>
                  </div>
                </div>

                <p className="text-xs text-text-secondary leading-relaxed">
                  {apiDetail?.description ?? tt.description}
                </p>

                {stanceEnum.length > 0 && (
                  <div>
                    <span className="text-xs text-text-muted">立场：</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {stanceEnum.map((s) => (
                        <span key={s} className="px-1.5 py-0.5 rounded text-[10px] bg-cyan/10 text-cyan">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {scoreDimensions.length > 0 && (
                  <div>
                    <span className="text-xs text-text-muted">评分维度：</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {scoreDimensions.map((d) => (
                        <span key={d} className="px-1.5 py-0.5 rounded text-[10px] bg-warm-orange/10 text-warm-orange">
                          {d}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                <div className="text-xs text-neon-green/60 group-hover:text-neon-green transition-colors mt-auto pt-1">
                  点击查看详情 →
                </div>
              </button>
            )
          })}
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={closeModal} />
          <div className="relative w-full max-w-lg rounded-2xl border border-border bg-bg-primary shadow-2xl animate-fade-in overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-border">
              <h2 className="text-lg font-semibold text-text-primary">任务类型详情</h2>
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
                  <p className="text-sm text-text-secondary">加载中...</p>
                </div>
              ) : selectedDetail ? (
                <div className="space-y-4">
                  <div>
                    <span className="text-xs text-text-muted">ID</span>
                    <p className="text-sm font-mono text-text-primary mt-0.5">{selectedDetail.task_type}</p>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">中文名称</span>
                    <p className="text-sm text-text-primary mt-0.5">{selectedDetail.name_zh}</p>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">描述</span>
                    <p className="text-sm text-text-secondary mt-0.5">{selectedDetail.description}</p>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">立场枚举 (stance_enum)</span>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {selectedDetail.stance_enum.map((s) => (
                        <span key={s} className="px-2 py-1 rounded-md text-xs bg-cyan/10 text-cyan border border-cyan/20">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">评分维度 (score_dimensions)</span>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {selectedDetail.score_dimensions.map((d) => (
                        <span key={d} className="px-2 py-1 rounded-md text-xs bg-warm-orange/10 text-warm-orange border border-warm-orange/20">
                          {d}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-xs text-text-muted">基础维度 (base_dimensions)</span>
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {selectedDetail.base_dimensions.map((d) => (
                        <span key={d} className="px-2 py-1 rounded-md text-xs bg-neon-green/10 text-neon-green border border-neon-green/20">
                          {d}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-text-muted text-center py-4">无法加载详情</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
