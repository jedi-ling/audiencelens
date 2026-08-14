import { useCallback, useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router'
import { cn } from '@/lib/utils'
import { NON_REVIEW_SKILL_TYPES, loadSkillTruth } from '@/lib/skills'
import type { SkillTruth } from '@/lib/skills'
import { AlertTriangle, ArrowRight, Layers, RefreshCw } from 'lucide-react'
import { PageShell, PageHeader, EmptyState, CARD_GRID_CLASS, PRIMARY_BUTTON_CLASS } from '@/components/ui'
import { t } from '@/i18n/runtime'
import { findTaskType, localizeBackendSkill } from '@/i18n/catalog'
import { useDocumentTitle } from '@/i18n/head'
import { tApiErrorParts } from '@/i18n/api-error'
import type { ApiErrorText } from '@/i18n/api-error'

export default function SkillSelectPage() {
  const navigate = useNavigate()
  useDocumentTitle('page.skills.meta.title')

  // 后端 /api/skills 是唯一事实源：哪些技能存在、叫什么、怎么描述，都以它为准。
  // 本地 SKILLS 只保留后端没有的展示装饰（图标/配色/用例）。名称和描述前端另存一份
  // 必然和引擎实际读的那份漂移，所以这里不再用本地的 name/description_zh。
  const [skills, setSkills] = useState<SkillTruth[] | null>(null)
  // 区分"后端说一个技能都没有"和"根本没加载上"：后者必须让用户看见，
  // 否则会被当成"我的技能没了"。
  // 存错误对象而不是拼好的字符串：拼好的那一刻语种就被冻住了，用户在错误态下
  // 切语言这句话不会跟着变。后端原文进 detail，由渲染处放 title 属性，
  // 不与英文界面并排显示（契约 D2）。
  const [error, setError] = useState<ApiErrorText | null>(null)
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
        setError(tApiErrorParts(e, 'error.fetch.skills'))
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
    <PageShell size="grid">
      <PageHeader
        center
        title={t('page.skills.header.title')}
        subtitle={
          <>
            {/* 原文是「不同技能提供差异化的评审策略和角色配置」，对 4 个技能一视同仁。
                实际只有红队对抗与受众面板会往提示词里加视角说明，合成试玩是默认流程、
                人格生成压根没接进评审。改成只承诺「换一种视角」这件确实发生的事。 */}
            {t('page.skills.header.subtitle')}
          </>
        }
      />

      {loading && (
        <div className={CARD_GRID_CLASS} aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-64 rounded-xl border border-border bg-bg-card animate-pulse" />
          ))}
        </div>
      )}

      {!loading && error && (
        <EmptyState
          icon={AlertTriangle}
          tone="error"
          title={t('page.skills.list_error.title')}
          // EmptyState.description 只收 string（components/ui 是 batch-0 的，不改它），
          // 所以后端原文没地方挂 title 属性。它不丢：非 zh 界面下 tApiErrorParts 已经
          // 把中文原文隔离在 detail 里不参与显示，这里只是不再额外露出——
          // 与"把中文和英文并排渲染"相比，这是两害相权取其轻。记进交付报告。
          description={t('page.skills.list_error.desc', { reason: error.text })}
          action={
            <button onClick={load} className={PRIMARY_BUTTON_CLASS}>
              <RefreshCw className="w-4 h-4" strokeWidth={1.5} />
              {t('page.skills.list_error.cta')}
            </button>
          }
        />
      )}

      {!loading && !error && skills?.length === 0 && (
        <EmptyState icon={Layers} title={t('page.skills.list.empty')} />
      )}

      {!loading && !error && skills && skills.length > 0 && (
        <div className={CARD_GRID_CLASS}>
          {skills.map((skill) => {
            const deco = skill.deco
            // 技能名与描述按 ui_lang 取。后端今天只回中文（catalog_en.py 已就位但
            // /api/skills 还没引用它），直接渲染 skill.name 在英文界面上就是
            // 「看不出是缺译的中文」。zh 仍用后端原文——后端是中文事实源，
            // 后端新增技能也照常显示。取法见 i18n/catalog.ts §B2。
            const skillText = localizeBackendSkill(skill)
            // 任务类型只认后端详情里的 task_types。这里以前用的是本地 SKILLS[].task_types，
            // 一份手写枚举：后端 apply_skill_hint / POST /api/v2/reviews 对
            // skill_type × task_type 的组合根本不做校验，这条「约束」在服务端不存在。
            // 名字仍从本地目录查（后端给的是 id），但改走 findTaskType：它按 ui_lang
            // 查 overlay，直读 TASK_TYPES[].name 的话英文界面上这一排标签全是中文。
            // 查不到的 id 仍然不渲染，计数直接用渲染结果的长度，
            // 保证「写的数」和「看得见的标签」永远一致。
            const taskNames = (skill.taskTypes ?? [])
              .map((tt) => findTaskType(tt)?.name)
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
                  // h-full + flex-col 让卡片在网格行内等高；底部 CTA 用 mt-auto 对齐基线
                  'group relative flex flex-col h-full p-6 rounded-xl border-2 transition-all duration-300 text-left',
                  'bg-bg-card',
                  border,
                  startsReview
                    ? 'hover:bg-bg-card-hover hover:shadow-lg'
                    : 'opacity-70 cursor-not-allowed'
                )}
              >
                <div className={cn('absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none', bg)} />

                <div className="relative z-10 flex flex-col flex-1">
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
                      <h2 className={cn('text-xl font-bold font-display', color)}>{skillText.name}</h2>
                      <span className="text-xs text-text-muted font-mono">{skill.type}</span>
                    </div>
                  </div>

                  <p className="text-sm text-text-secondary leading-relaxed mb-5">
                    {skillText.description}
                  </p>

                  {/* 这里以前还有一个"N 个角色"。它来自前端写死的 persona_count，
                      后端没有任何对应字段，其中 persona_generate 标的 10 甚至超过了
                      所有评审模式的人数上限（REVIEW_MODES 最大 8），是个可被证伪的假数。
                      真实人数由用户在创建评审时选的模式决定，这一页根本不知道，所以不显示。 */}
                  {taskNames.length > 0 && (
                    <div className="mb-5">
                      <h3 className="text-xs font-medium text-text-muted mb-2">
                        {t('page.skills.card_task_types.label', { count: taskNames.length })}
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

                  {/* ⚠ use_cases 是 mock-data 的 SKILLS[].use_cases，纯前端展示装饰、
                      后端没有对应字段，也不在后端目录 catalog.en-US.json 里，
                      所以 i18n:sync-catalog 生成不出它——英文界面上这四个标签今天仍是中文。
                      它要么进一份手写的前端 overlay（与 EVALUATION_DIMENSIONS 同级），
                      要么后端在 /api/skills/{skill_type} 里透出来。两条都不是本次接线的
                      文件范围，已写进交付报告，不在这里就地 t() 一份（那会立第二个 owner）。 */}
                  {deco && deco.use_cases.length > 0 && (
                    <div className="mb-5">
                      <h3 className="text-xs font-medium text-text-muted mb-2">
                        {t('page.skills.card_use_cases.label')}
                      </h3>
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
                    <div className={cn('mt-auto flex items-center gap-2 text-sm font-medium transition-colors', color)}>
                      <span>{t('page.skills.card.cta')}</span>
                      <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" strokeWidth={1.25} />
                    </div>
                  ) : (
                    <div className="mt-auto flex items-start gap-2 text-xs text-text-muted leading-relaxed">
                      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.5} />
                      <span>{t('page.skills.card_disabled.hint')}</span>
                    </div>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      )}
    </PageShell>
  )
}
