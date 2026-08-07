import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { cn } from '@/lib/utils'
import { SKILLS, TASK_TYPES } from '@/lib/mock-data'
import type { SkillType } from '@/lib/mock-data'
import { fetchSkills } from '@/lib/api'
import { ArrowRight, Layers, Users } from 'lucide-react'

export default function SkillSelectPage() {
  const navigate = useNavigate()

  // 后端 /api/skills 是"哪些技能可用"的事实源；本地 SKILLS 只负责 UI 装饰
  // （图标/配色/用例文案）。API 挂了就回落本地全量列表，页面不白屏。
  const [availableTypes, setAvailableTypes] = useState<Set<string> | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchSkills()
      .then((list) => {
        if (!cancelled) setAvailableTypes(new Set(list.map((s) => s.skill_type)))
      })
      .catch(() => {
        if (!cancelled) setAvailableTypes(null)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const skills = availableTypes ? SKILLS.filter((s) => availableTypes.has(s.type)) : SKILLS

  const handleSelectSkill = (skillType: SkillType) => {
    navigate(`/review/new?skill=${skillType}`)
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 animate-fade-in">
      <div className="text-center mb-10">
        <h1 className="font-display text-3xl md:text-4xl font-bold text-gradient-green mb-3">
          技能中心
        </h1>
        <p className="text-text-secondary max-w-2xl mx-auto">
          选择评审技能，不同技能提供差异化的评审策略和角色配置，覆盖从试玩验证到对抗测试的完整场景
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {skills.map((skill) => {
          const relatedTaskCount = skill.task_types.length
          const relatedTaskNames = skill.task_types
            .map((tt) => TASK_TYPES.find((t) => t.id === tt)?.name)
            .filter(Boolean)

          return (
            <button
              key={skill.type}
              onClick={() => handleSelectSkill(skill.type)}
              className={cn(
                'group relative flex flex-col p-6 rounded-2xl border-2 transition-all duration-300 text-left',
                'bg-bg-card hover:bg-bg-card-hover',
                skill.border,
                'hover:scale-[1.02] hover:shadow-lg'
              )}
            >
              <div className={cn('absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none', skill.bg)} />

              <div className="relative z-10">
                <div className="flex items-center gap-3 mb-4">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-primary/10 border border-brand-primary/20">
                    <img
                      src={skill.icon}
                      alt={skill.name}
                      className="h-7 w-7 object-contain drop-shadow-[0_2px_8px_rgba(0,113,227,0.3)]"
                      loading="lazy"
                    />
                  </span>
                  <div>
                    <h2 className={cn('text-xl font-bold font-display', skill.color)}>
                      {skill.name}
                    </h2>
                    <span className="text-xs text-text-muted font-mono">{skill.type}</span>
                  </div>
                </div>

                <p className="text-sm text-text-secondary leading-relaxed mb-5">
                  {skill.description_zh}
                </p>

                <div className="flex items-center gap-4 mb-4">
                  <div className="flex items-center gap-1.5 text-xs text-text-muted">
                    <Layers className="w-3.5 h-3.5" strokeWidth={1.25} />
                    <span>{relatedTaskCount} 种任务类型</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-text-muted">
                    <Users className="w-3.5 h-3.5" strokeWidth={1.25} />
                    <span>{skill.persona_count} 个角色</span>
                  </div>
                </div>

                <div className="mb-5">
                  <h3 className="text-xs font-medium text-text-muted mb-2">适用任务</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {relatedTaskNames.map((name) => (
                      <span
                        key={name}
                        className={cn('px-2 py-0.5 rounded text-xs', skill.bg, skill.color)}
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="mb-5">
                  <h3 className="text-xs font-medium text-text-muted mb-2">典型用例</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {skill.use_cases.map((uc) => (
                      <span
                        key={uc}
                        className="px-2 py-0.5 rounded text-xs bg-bg-secondary text-text-secondary"
                      >
                        {uc}
                      </span>
                    ))}
                  </div>
                </div>

                <div className={cn(
                  'flex items-center gap-2 text-sm font-medium transition-colors',
                  skill.color
                )}>
                  <span>使用此技能创建评审</span>
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" strokeWidth={1.25} />
                </div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}
