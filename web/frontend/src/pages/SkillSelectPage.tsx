import { useCallback, useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router'
import { cn } from '@/lib/utils'
import { TASK_TYPES } from '@/lib/mock-data'
import { NON_REVIEW_SKILL_TYPES, loadSkillTruth } from '@/lib/skills'
import type { SkillTruth } from '@/lib/skills'
import { AlertTriangle, ArrowRight, Layers, RefreshCw } from 'lucide-react'

export default function SkillSelectPage() {
  const navigate = useNavigate()

  // 后端 /api/skills 是唯一事实源：哪些技能存在、叫什么、怎么描述，都以它为准。
  // 本地 SKILLS 只保留后端没有的展示装饰（图标/配色/用例）。名称和描述前端另存一份
  // 必然和引擎实际读的那份漂移，所以这里不再用本地的 name/description_zh。
  const [skills, setSkills] = useState<SkillTruth[] | null>(null)
  // 区分"后端说一个技能都没有"和"根本没加载上"：后者必须让用户看见，
  // 否则会被当成"我的技能没了"。
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // 用递增的请求序号而不是每次调用各自的 cancelled 标志：后者只能在
  // useEffect 卸载时生效，手动点"重新加载"拿到的清理函数没人调用，
  // 于是连点两次会有两个在途请求，先发的若后到就会覆盖后发的结果。
  const reqSeq = useRef(0)

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    const myReq = ++reqSeq.current
    let cancelled = false
    const stale = () => cancelled || myReq !== reqSeq.current
    loadSkillTruth()
      .then((list) => {
        if (stale()) return
        setSkills(list)
        setLoading(false)
      })
      .catch((e: unknown) => {
        if (stale()) return
        // 失败时不要退化成"本地全量列表"：那会把一份可能已经和后端不一致的
        // 名单当成真的展示出去，用户点进去才发现技能不可用。
        setSkills(null)
        setError(e instanceof Error ? e.message : '加载技能列表失败')
        setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => load(), [load])

  const handleSelectSkill = (skillType: string) => {
    // 不做 `as SkillType` 断言：这个值来自后端，后端新增技能时断言只是
    // 让类型检查闭嘴，并不能让它真的属于那个联合类型——是类型层面的谎报。
    // 它在这里只是拼进 URL，用 string 才是诚实的。
    navigate(`/review/new?skill=${encodeURIComponent(skillType)}`)
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 animate-fade-in">
      <div className="text-center mb-10">
        <h1 className="font-display text-3xl md:text-4xl font-bold text-gradient-green mb-3">
          技能中心
        </h1>
        <p className="text-text-secondary max-w-2xl mx-auto">
          {/* 原文是「不同技能提供差异化的评审策略和角色配置」，对 4 个技能一视同仁。
              实际只有红队对抗与受众面板会往提示词里加视角说明，合成试玩是默认流程、
              人格生成压根没接进评审。改成只承诺「换一种视角」这件确实发生的事。 */}
          选择评审技能：技能决定评审员以哪种视角来看你的材料，具体人数和角色仍由你在创建评审时选择
        </p>
      </div>

      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-64 rounded-2xl border-2 border-border bg-bg-card animate-pulse" />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="rounded-2xl border-2 border-red-500/30 bg-red-500/5 p-8 text-center">
          <AlertTriangle className="w-8 h-8 mx-auto mb-3 text-red-500" strokeWidth={1.25} />
          <h2 className="font-display text-lg font-bold mb-1">技能列表没能加载出来</h2>
          <p className="text-sm text-text-secondary mb-4">{error}</p>
          <p className="text-xs text-text-muted mb-5">
            这不代表你的技能被停用了，只是这次没取到列表，请重试。
          </p>
          <button
            onClick={load}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-primary text-white text-sm font-medium hover:opacity-90 transition-opacity"
          >
            <RefreshCw className="w-4 h-4" strokeWidth={1.5} />
            重新加载
          </button>
        </div>
      )}

      {!loading && !error && skills?.length === 0 && (
        <div className="rounded-2xl border-2 border-border bg-bg-card p-8 text-center text-sm text-text-secondary">
          当前账号下没有可用的评审技能。
        </div>
      )}

      {!loading && !error && skills && skills.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {skills.map((skill) => {
            const deco = skill.deco
            // 任务类型只认后端详情里的 task_types。这里以前用的是本地 SKILLS[].task_types，
            // 一份手写枚举：后端 apply_skill_hint / POST /api/v2/reviews 对
            // skill_type × task_type 的组合根本不做校验，这条「约束」在服务端不存在。
            // 名字仍从本地 TASK_TYPES 查（后端给的是 id），查不到的 id 不渲染，
            // 计数直接用渲染结果的长度，保证「写的数」和「看得见的标签」永远一致。
            const taskNames = (skill.taskTypes ?? [])
              .map((tt) => TASK_TYPES.find((t) => t.id === tt)?.name)
              .filter((n): n is string => Boolean(n))

            const color = deco?.color ?? 'text-brand-primary'
            const bg = deco?.bg ?? 'bg-brand-primary/10'
            const border = deco?.border ?? 'border-brand-primary/30'
            const startsReview = !NON_REVIEW_SKILL_TYPES.includes(skill.type)

            return (
              <button
                key={skill.type}
                onClick={() => startsReview && handleSelectSkill(skill.type)}
                // 不能创建评审的技能，按钮就真的不可点：留一个点了没用的入口，
                // 用户的代价是一次评审额度加一份答非所问的报告。
                disabled={!startsReview}
                aria-disabled={!startsReview}
                className={cn(
                  'group relative flex flex-col p-6 rounded-2xl border-2 transition-all duration-300 text-left',
                  'bg-bg-card',
                  border,
                  startsReview
                    ? 'hover:bg-bg-card-hover hover:scale-[1.02] hover:shadow-lg'
                    : 'opacity-70 cursor-not-allowed'
                )}
              >
                <div className={cn('absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none', bg)} />

                <div className="relative z-10">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-primary/10 border border-brand-primary/20">
                      {deco ? (
                        <img
                          src={deco.icon}
                          alt=""
                          className="h-7 w-7 object-contain drop-shadow-[0_2px_8px_rgba(0,113,227,0.3)]"
                          loading="lazy"
                        />
                      ) : (
                        <Layers className="w-6 h-6 text-brand-primary" strokeWidth={1.25} />
                      )}
                    </span>
                    <div>
                      <h2 className={cn('text-xl font-bold font-display', color)}>{skill.name}</h2>
                      <span className="text-xs text-text-muted font-mono">{skill.type}</span>
                    </div>
                  </div>

                  <p className="text-sm text-text-secondary leading-relaxed mb-5">
                    {skill.description}
                  </p>

                  {/* 这里以前还有一个"N 个角色"。它来自前端写死的 persona_count，
                      后端没有任何对应字段，其中 persona_generate 标的 10 甚至超过了
                      所有评审模式的人数上限（REVIEW_MODES 最大 8），是个可被证伪的假数。
                      真实人数由用户在创建评审时选的模式决定，这一页根本不知道，所以不显示。 */}
                  {taskNames.length > 0 && (
                    <div className="mb-5">
                      <h3 className="text-xs font-medium text-text-muted mb-2">
                        可选任务类型（{taskNames.length}）
                      </h3>
                      <div className="flex flex-wrap gap-1.5">
                        {taskNames.map((name) => (
                          <span key={name} className={cn('px-2 py-0.5 rounded text-xs', bg, color)}>
                            {name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {deco && deco.use_cases.length > 0 && (
                    <div className="mb-5">
                      <h3 className="text-xs font-medium text-text-muted mb-2">典型用例</h3>
                      <div className="flex flex-wrap gap-1.5">
                        {deco.use_cases.map((uc) => (
                          <span
                            key={uc}
                            className="px-2 py-0.5 rounded text-xs bg-bg-secondary text-text-secondary"
                          >
                            {uc}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {startsReview ? (
                    <div className={cn('flex items-center gap-2 text-sm font-medium transition-colors', color)}>
                      <span>使用此技能创建评审</span>
                      <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" strokeWidth={1.25} />
                    </div>
                  ) : (
                    <div className="flex items-start gap-2 text-xs text-text-muted leading-relaxed">
                      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.5} />
                      <span>
                        该技能还没有接入评审流程：从这里创建评审不会改变评审的跑法，
                        所以入口先关掉，等它真正可用再开放。
                      </span>
                    </div>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
