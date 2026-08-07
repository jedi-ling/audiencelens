import { useState, useEffect, useMemo } from 'react'
import { usePersonaStore } from '@/store/persona-store'
import { cn } from '@/lib/utils'
import PersonaRadarChart from '@/components/PersonaRadarChart'
import { Search, X, GitCompare, ChevronDown, ChevronUp, Loader2, SlidersHorizontal } from 'lucide-react'
import { PACK_CATEGORIES } from '@/lib/mock-data'

export default function PersonasPage() {
  const {
    personas,
    packs,
    selectedPack,
    compareIds,
    searchQuery,
    initialized,
    setSelectedPack,
    setCompareIds,
    setSearchQuery,
    initPersonas,
  } = usePersonaStore()

  useEffect(() => {
    if (!initialized) initPersonas()
  }, [initialized, initPersonas])

  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {}
    PACK_CATEGORIES.forEach((cat) => { initial[cat.id] = true })
    return initial
  })

  const packsByCategory = useMemo(() => {
    const grouped: Record<string, typeof packs> = {}
    PACK_CATEGORIES.forEach((cat) => { grouped[cat.id] = [] })
    packs.forEach((pack) => {
      const catId = pack.category || 'special'
      if (!grouped[catId]) grouped[catId] = []
      grouped[catId].push(pack)
    })
    return grouped
  }, [packs])

  const toggleCategory = (categoryId: string) => {
    setExpandedCategories((prev) => ({ ...prev, [categoryId]: !prev[categoryId] }))
  }

  const filteredPersonas = personas.filter((p) => {
    const matchPack = !selectedPack || p.pack === selectedPack
    const matchSearch = !searchQuery ||
      p.name.includes(searchQuery) ||
      p.archetype.includes(searchQuery) ||
      p.identity_summary.includes(searchQuery)
    return matchPack && matchSearch
  })

  const compareMode = compareIds !== null
  const comparePersonas = compareIds
    ? personas.filter((p) => compareIds.includes(p.id))
    : []

  const toggleCompare = (id: string) => {
    if (!compareIds) {
      setCompareIds([id, ''])
      return
    }
    if (compareIds[0] === id) {
      setCompareIds(null)
      return
    }
    if (compareIds[1] === id) {
      setCompareIds([compareIds[0], ''])
      return
    }
    if (!compareIds[1]) {
      setCompareIds([compareIds[0], id])
      return
    }
    setCompareIds([compareIds[1], id])
  }

  const sidebarContent = (
    <>
      <h3 className="text-sm font-medium text-text-muted mb-3">角色包筛选</h3>
      <div className="flex flex-col gap-1.5">
        <button
          onClick={() => { setSelectedPack(null); setDrawerOpen(false) }}
          className={cn(
            'text-left px-3 py-2 rounded-lg text-sm transition-all',
            !selectedPack
              ? 'bg-brand-primary/10 text-brand-primary border-l-2 border-brand-primary'
              : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
          )}
        >
          全部 <span className="text-text-muted">{personas.length}</span>
        </button>

        {PACK_CATEGORIES.map((category) => {
          const categoryPacks = packsByCategory[category.id] || []
          if (categoryPacks.length === 0) return null
          const isExpanded = expandedCategories[category.id] !== false

          return (
            <div key={category.id} className="mt-3 first:mt-0">
              <button
                onClick={() => toggleCategory(category.id)}
                className="flex items-center justify-between w-full px-1 py-1.5 text-xs font-medium text-text-muted uppercase tracking-wider hover:text-text-secondary transition-colors"
              >
                <span>{category.name}</span>
                <span className="flex items-center gap-1.5">
                  <span className="text-[10px] normal-case tracking-normal opacity-60">{categoryPacks.length}</span>
                  {isExpanded ? (
                    <ChevronUp className="w-3.5 h-3.5" strokeWidth={1.25} />
                  ) : (
                    <ChevronDown className="w-3.5 h-3.5" strokeWidth={1.25} />
                  )}
                </span>
              </button>

              <div className={cn(
                'flex flex-col gap-1.5 overflow-hidden transition-all duration-200',
                isExpanded ? 'max-h-[1000px] opacity-100 mt-1.5' : 'max-h-0 opacity-0'
              )}>
                {categoryPacks.map((pack) => {
                  const packCount = personas.filter((p) => p.pack === pack.panel_id).length
                  return (
                    <button
                      key={pack.panel_id}
                      onClick={() => { setSelectedPack(selectedPack === pack.panel_id ? null : pack.panel_id); setDrawerOpen(false) }}
                      className={cn(
                        'text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center gap-2',
                        selectedPack === pack.panel_id
                          ? 'bg-brand-primary/10 text-brand-primary border-l-2 border-brand-primary'
                          : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'
                      )}
                    >
                      <span>{pack.name}</span>
                      <span className="text-text-muted">{packCount}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </>
  )

  if (!initialized) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center">
        <Loader2 className="w-8 h-8 text-cyan animate-spin mx-auto mb-4" strokeWidth={1.25} />
        <p className="text-text-secondary">加载角色数据...</p>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-text-primary font-display">角色浏览</h1>
          <button
            onClick={() => setDrawerOpen(true)}
            className="md:hidden flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-sm bg-bg-card border border-border text-text-secondary hover:border-cyan/30 hover:text-cyan transition-all"
          >
            <SlidersHorizontal className="w-4 h-4" strokeWidth={1.25} />
            筛选
          </button>
        </div>
        <button
          onClick={() => setCompareIds(compareIds ? null : ['', ''])}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all',
            compareMode
              ? 'bg-cyan/10 text-cyan border border-cyan/30'
              : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30 hover:text-cyan'
          )}
        >
          <GitCompare className="w-4 h-4" strokeWidth={1.25} />
          {compareMode ? '退出对比' : '对比模式'}
        </button>
      </div>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/25 backdrop-blur-sm"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="absolute bottom-0 left-0 right-0 bg-bg-primary border-t border-border rounded-t-2xl max-h-[70vh] overflow-y-auto p-5 animate-fade-in">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-text-primary">角色包筛选</h3>
              <button
                onClick={() => setDrawerOpen(false)}
                className="p-1.5 rounded-lg hover:bg-bg-card text-text-muted hover:text-text-primary transition-colors"
              >
                <X className="w-4 h-4" strokeWidth={1.25} />
              </button>
            </div>
            {sidebarContent}
          </div>
        </div>
      )}

      {compareMode && comparePersonas.length === 2 && (
        <div className="rounded-xl border border-cyan/30 bg-bg-card p-4 md:p-6 mb-6 glow-cyan">
          <h3 className="text-sm font-medium text-cyan mb-4 font-display">角色对比</h3>
          <div className="flex items-center justify-center">
            <PersonaRadarChart
              data={comparePersonas[0].behavior_profile}
              compareData={comparePersonas[1].behavior_profile}
              name1={comparePersonas[0].name}
              name2={comparePersonas[1].name}
              size={280}
              mobileSize={200}
            />
          </div>
          <div className="flex justify-center gap-8 mt-4">
            {comparePersonas.map((p) => (
              <div key={p.id} className="text-center">
                <p className="font-medium text-text-primary">{p.name}</p>
                <p className="text-xs text-text-muted">{p.archetype}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col md:flex-row gap-6">
        <div className="hidden md:block md:w-56 shrink-0">
          <div className="sticky top-20">
            {sidebarContent}
          </div>
        </div>

        <div className="flex-1">
          <div className="mb-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" strokeWidth={1.25} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索角色..."
                className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-cyan/50 transition-colors text-sm"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                >
                  <X className="w-4 h-4 text-text-muted hover:text-text-primary" strokeWidth={1.25} />
                </button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 items-start">
            {filteredPersonas.map((persona) => {
              const isExpanded = expandedId === persona.id
              const isCompareSelected = compareIds?.includes(persona.id)

              return (
                <div
                  key={persona.id}
                  className={cn(
                    'rounded-xl border-2 bg-bg-card overflow-hidden transition-all',
                    isCompareSelected ? 'border-cyan/50 glow-cyan' :
                    isExpanded ? 'border-brand-primary/30' : 'border-border'
                  )}
                >
                  <div
                    className="p-4 cursor-pointer hover:bg-bg-card-hover transition-colors"
                    onClick={() => setExpandedId(isExpanded ? null : persona.id)}
                  >
                    <div className="flex items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-text-primary">{persona.name}</span>
                          <span className="text-xs text-text-muted">{persona.archetype}</span>
                        </div>
                        <p className="text-xs text-text-secondary line-clamp-2">{persona.identity_summary}</p>
                      </div>
                      <div className="shrink-0">
                        <PersonaRadarChart data={persona.behavior_profile} size={80} mobileSize={60} />
                      </div>
                    </div>

                    <div className="flex items-center justify-between mt-3">
                      <span className="text-xs text-text-muted">
                        {packs.find((p) => p.panel_id === persona.pack)?.name ?? '未知'}
                      </span>
                      <div className="flex items-center gap-2">
                        {compareMode && (
                          <button
                            onClick={(e) => { e.stopPropagation(); toggleCompare(persona.id) }}
                            className={cn(
                              'text-xs px-2 py-0.5 rounded transition-colors',
                              isCompareSelected
                                ? 'bg-cyan/20 text-cyan'
                                : 'bg-bg-secondary text-text-muted hover:text-cyan'
                            )}
                          >
                            对比
                          </button>
                        )}
                        {isExpanded ? (
                          <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                        )}
                      </div>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-border pt-3 animate-fade-in">
                      <div className="flex justify-center mb-4">
                        <PersonaRadarChart data={persona.behavior_profile} size={200} mobileSize={160} />
                      </div>

                      {persona.decisionRules && persona.decisionRules.length > 0 && (
                        <div className="mb-3">
                          <h4 className="text-xs font-medium text-text-muted mb-1.5 font-display">决策规则</h4>
                          <ul className="space-y-1">
                            {persona.decisionRules.map((rule, i) => (
                              <li key={i} className="text-xs text-text-secondary flex items-start gap-1.5">
                                <span className="text-brand-primary mt-0.5">▸</span>
                                {rule}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {persona.triggers && persona.triggers.length > 0 && (
                        <div>
                          <h4 className="text-xs font-medium text-text-muted mb-1.5 font-display">触发器</h4>
                          <div className="flex flex-wrap gap-1.5">
                            {persona.triggers.map((trigger, i) => (
                              <span key={i} className="px-2 py-0.5 rounded bg-bg-secondary text-text-secondary border border-border text-xs">
                                {trigger}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {filteredPersonas.length === 0 && (
            <div className="text-center py-12 text-text-muted">
              <p>没有匹配的角色</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
