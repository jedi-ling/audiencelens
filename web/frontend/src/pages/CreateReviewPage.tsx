import { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { cn } from '@/lib/utils'
import { TASK_TYPES, PACK_ICONS, TASK_MATERIALS, TASK_TYPE_CATEGORIES, REVIEW_MODES, SKILLS } from '@/lib/mock-data'
import type { Persona, TaskMaterialField, Example, ReviewMode, SkillType } from '@/lib/mock-data'
import { extractMaterials } from '@/lib/api'
import { usePersonaStore } from '@/store/persona-store'
import { useReviewStore } from '@/store/review-store'
import TaskTypeCard from '@/components/TaskTypeCard'
import PersonaRadarChart from '@/components/PersonaRadarChart'
import { ArrowLeft, ArrowRight, Upload, CheckCircle2, X, Loader2, ChevronDown, ChevronUp, Star, AlignLeft, FileText, Shield, FlaskConical, AlertTriangle } from 'lucide-react'

type Step = 0 | 1 | 2 | 3 | 4 | 5
/**
 * 材料只有两种来源：手填文本、上传文件。
 *
 * 这里曾经有第三种 'directory'（"目录路径"）：把用户敲进来的本地路径塞进
 * artifact_bundle.directory_path 落库，UI 还写着"系统将自动扫描目录中的文件
 * 并提取评审材料"。实际上 directory_path 在 web/backend 与 src/runner 里
 * 零消费点（grep 全仓只有这一处写入），一行都没人读——收集了却没人用，
 * 等于骗用户填。
 *
 * 而且它在浏览器形态下**根本不可能成立**：评审跑在服务器上，服务器访问不到
 * 用户机器上的路径；真要支持"整个项目一起评"，只能是前端把目录里的文件读出来
 * 逐个上传（走已有的 /api/uploads + 抽取链路），而不是传一个字符串路径过去。
 * 所以这个模式整体下线，等真做出目录上传再回来。
 */
type MaterialInputMode = 'text' | 'file'

const modeConfig: Record<ReviewMode, { label: string; color: string; bg: string; border: string; icon: string }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', border: 'border-cyan/30', icon: '⚡' },
  standard: { label: '标准', color: 'text-brand-primary', bg: 'bg-brand-primary/10', border: 'border-brand-primary/30', icon: '✅' },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', border: 'border-warm-orange/30', icon: '🔬' },
}

/**
 * SKILLS[].icon 存的是**图片路径**（'/skills/skill-game.png'），不是 emoji。
 * 这三处以前写成 <span className="text-2xl">{skill.icon}</span>，页面上直接
 * 显示出那串路径文本。渲染方式与 SkillSelectPage 统一成 <img>。
 */
function SkillIcon({ skill, className }: { skill: (typeof SKILLS)[number]; className?: string }) {
  return (
    <img
      src={skill.icon}
      alt={skill.name}
      className={cn('object-contain', className)}
      loading="lazy"
    />
  )
}

export default function CreateReviewPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const preselectedSkill = searchParams.get('skill') as SkillType | null
  const requestedTask = searchParams.get('task')
  const preselectedTask = TASK_TYPES.some((task) => task.id === requestedTask) ? requestedTask : null
  const inferredSkill = preselectedTask
    ? SKILLS.find((skill) => skill.task_types.includes(preselectedTask))?.type ?? null
    : null
  const [step, setStep] = useState<Step>(preselectedTask ? 2 : preselectedSkill ? 1 : 0)
  const [selectedSkillType, setSelectedSkillType] = useState<SkillType | null>(preselectedSkill ?? inferredSkill)
  const [selectedTaskType, setSelectedTaskType] = useState<string | null>(preselectedTask)
  const [selectedCategory, setSelectedCategory] = useState<string>('development')
  const [selectedMode, setSelectedMode] = useState<ReviewMode>('standard')
  const [target, setTarget] = useState('')
  const [materialFields, setMaterialFields] = useState<Record<string, string>>({})
  const [materialInputMode, setMaterialInputMode] = useState<MaterialInputMode>('text')
  const [selectedPack, setSelectedPack] = useState<string | null>(null)
  const [selectedPersonaIds, setSelectedPersonaIds] = useState<Set<string>>(new Set())
  const [launching, setLaunching] = useState(false)
  const [launchError, setLaunchError] = useState<string | null>(null)
  const [materialsExpanded, setMaterialsExpanded] = useState(false)
  const [examplesExpanded, setExamplesExpanded] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [extractError, setExtractError] = useState<string | null>(null)
  const [enableEvaluation, setEnableEvaluation] = useState(false)
  const [enableRedTeam, setEnableRedTeam] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { personas, packs, initPersonas, initialized } = usePersonaStore()
  const { examples, fetchExamplesList, createNewReview } = useReviewStore()

  useEffect(() => {
    if (!initialized) initPersonas()
  }, [initialized, initPersonas])

  useEffect(() => {
    fetchExamplesList()
  }, [fetchExamplesList])

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [step])

  const handleImportExample = (example: Example) => {
    setTarget(example.artifact_bundle.title || '')
    const fields: Record<string, string> = {}
    for (const m of example.artifact_bundle.materials || []) {
      if (m.type && m.description) {
        fields[m.type] = m.description
      }
    }
    setMaterialFields(fields)
  }

  const currentFields: TaskMaterialField[] = selectedTaskType
    ? TASK_MATERIALS[selectedTaskType] ?? []
    : []

  const filteredTaskTypes = selectedSkillType
    ? TASK_TYPES.filter((tt) => {
        const skill = SKILLS.find((s) => s.type === selectedSkillType)
        return skill ? skill.task_types.includes(tt.id) : true
      })
    : TASK_TYPES

  const requiredFields = currentFields.filter((f) => f.required)

  const currentModeConfig = REVIEW_MODES.find((m) => m.mode === selectedMode)
  const selectedPersonas = personas.filter((p) => selectedPersonaIds.has(p.id))

  /* ---------------- 「选了谁」必须等于「跑了谁」 ----------------
   *
   * 后端 PersonaService.select_panel_by_mode 是这么干的：先按 persona_pack
   * 取出该包的人格列表，再在**这个列表内**按 id 过滤 selected_personas，
   * 最后 selected[:max_count] 截断。于是过去有两种组合会被静默改写：
   *
   *   1. 跨包混选：第 3 步未选包时列表展示全部包的人格，提交时 persona_pack
   *      被兜底成 game-core，别的包的人格一个都匹配不上 → 整批丢弃 → 引擎回落
   *      自动选人。而第 5 步确认页仍然显示着用户挑的人名，报告里却是另一批人。
   *   2. 超过模式上限：截断取的是**包内顺序**的前 N 个，不是用户勾选顺序，
   *      被丢掉的是谁完全不可预期。
   *
   * 两种都在提交前拦住并说清楚原因，而不是让用户事后从报告里发现人对不上。
   */
  const selectedPackIds = Array.from(new Set(selectedPersonas.map((p) => p.pack ?? 'game-core')))
  /** 真正提交的包：显式选了就用它，否则由所选人格反推（只有全部同包时才推得出） */
  const effectivePack = selectedPack ?? (selectedPackIds.length === 1 ? selectedPackIds[0] : null)
  /** 选中的人格横跨多个包，或与显式选定的包不一致——两者都会被后端过滤掉一部分 */
  const packConflict =
    selectedPersonaIds.size > 0 &&
    (selectedPackIds.length > 1 || (selectedPack !== null && selectedPackIds[0] !== selectedPack))
  const modeMax = currentModeConfig?.persona_count_range[1] ?? 8
  const overModeMax = selectedPersonaIds.size > modeMax
  const packName = (id: string) => packs.find((p) => p.panel_id === id)?.name ?? id

  const stepLabels: Record<Step, string> = {
    0: '选择技能',
    1: '选择任务类型',
    2: '上传材料',
    3: '选择角色',
    4: '评审选项',
    5: '确认并启动',
  }

  const canNext = () => {
    if (step === 0) return selectedSkillType !== null
    if (step === 1) return selectedTaskType !== null
    if (step === 2) {
      if (target.trim() === '') return false
      return requiredFields.every((f) => (materialFields[f.key] ?? '').trim() !== '')
    }
    // 会被后端静默改写的组合一律不放行——原因就在按钮上方的横幅里写着
    if (step === 3) return selectedPersonaIds.size > 0 && !packConflict && !overModeMax && effectivePack !== null
    if (step === 4) return true
    return true
  }

  const handleNext = () => {
    if (step < 5 && canNext()) setStep((step + 1) as Step)
  }

  const handlePrev = () => {
    if (step > 0) setStep((step - 1) as Step)
  }

  const handleLaunch = async () => {
    if (!selectedTaskType) return
    // 第 3 步已经拦过一道，这里是最后一道闸：宁可不发请求，也不能发一个
    // "跑出来跟确认页不一样"的评审出去
    if (!effectivePack || packConflict || overModeMax) {
      setLaunchError('所选角色与角色包/评审模式不一致，请返回第 3 步调整后再启动')
      setStep(3)
      return
    }
    setLaunching(true)
    setLaunchError(null)
    try {
      const materials = Object.entries(materialFields)
        .filter(([, value]) => value.trim() !== '')
        .map(([type, description]) => ({ type, description }))

      const artifactBundle: Record<string, unknown> = {
        title: target,
        type: selectedTaskType,
        description: materialFields['一句话pitch'] || materialFields['核心循环说明'] || target,
        materials,
      }

      // 走 v2 异步链路（Job 队列 + WS 进度）。此前走 v1 同步接口：阻塞线程池、
      // 无视 BYOK key、无 key 时把模拟数据当真实报告入库——三个坑一次躲掉。
      const reviewId = await createNewReview({
        task_type: selectedTaskType,
        // effectivePack 而不是 selectedPack：未显式选包时由所选人格反推，
        // 保证后端按这个包过滤时一个人都不会被丢掉
        persona_pack: effectivePack,
        artifact_bundle: artifactBundle,
        selected_personas: Array.from(selectedPersonaIds),
        mode: selectedMode,
        skill_type: selectedSkillType ?? undefined,
        // 这两个开关此前从 UI 传到后端被 schema 静默丢弃、从未生效——现在真接上了：
        // enable_evaluation 评审完成后自动跑 8 维评估，enable_red_team 叠加对抗视角提示
        enable_evaluation: enableEvaluation,
        enable_red_team: enableRedTeam,
      })
      navigate(`/review/${reviewId}`)
    } catch (e) {
      setLaunchError(e instanceof Error ? e.message : '发起评审失败')
    } finally {
      setLaunching(false)
    }
  }

  const updateField = (key: string, value: string) => {
    setMaterialFields((prev) => ({ ...prev, [key]: value }))
  }

  const handleFileUpload = async (file: File) => {
    if (!selectedTaskType) return
    setExtracting(true)
    setExtractError(null)
    try {
      const result = await extractMaterials(selectedTaskType, file)
      if (result.title) {
        setTarget(result.title)
      }
      setMaterialFields((prev) => {
        const next = { ...prev }
        for (const [key, value] of Object.entries(result.materials)) {
          if (value) {
            next[key] = value
          }
        }
        return next
      })
    } catch {
      setExtractError('AI 提取失败，请手动填写材料')
    } finally {
      setExtracting(false)
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return
    for (const file of Array.from(files)) {
      handleFileUpload(file)
    }
    e.target.value = ''
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const files = e.dataTransfer.files
    for (const file of Array.from(files)) {
      handleFileUpload(file)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
  }

  const togglePersona = (id: string) => {
    setSelectedPersonaIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const filteredPersonas = selectedPack
    ? personas.filter((p) => p.pack === selectedPack)
    : personas

  const filledMaterialsCount = Object.entries(materialFields).filter(([, v]) => v.trim() !== '').length

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 animate-fade-in">
      <div className="flex items-center gap-2 md:gap-4 mb-8">
        {Array.from({ length: 6 }, (_, i) => i).map((s) => (
          <div key={s} className="flex items-center gap-1 md:gap-2 flex-1">
            <div
              className={cn(
                'w-7 h-7 md:w-8 md:h-8 rounded-full flex items-center justify-center text-xs md:text-sm font-mono font-bold shrink-0 transition-all',
                s < step
                  ? 'bg-brand-primary text-white'
                  : s === step
                    ? 'bg-brand-primary/20 text-brand-primary border-2 border-brand-primary'
                    : 'bg-bg-card text-text-muted border border-border'
              )}
            >
              {s < step ? <CheckCircle2 className="w-3.5 h-3.5 md:w-4 md:h-4" strokeWidth={1.25} /> : s}
            </div>
            <span className={cn(
              'text-xs md:text-sm hidden md:inline font-display',
              s <= step ? 'text-text-primary' : 'text-text-muted'
            )}>
              {stepLabels[s as Step]}
            </span>
            <span className={cn(
              'text-xs md:hidden font-display',
              s === step ? 'text-text-primary' : 'text-text-muted'
            )}>
              {s === step ? `${s}/5` : ''}
            </span>
            {s < 5 && (
              <div className={cn(
                'flex-1 min-w-2 md:min-w-4 h-px',
                s < step ? 'bg-gradient-to-r from-brand-primary/60 to-brand-primary' : 'bg-border'
              )} />
            )}
          </div>
        ))}
      </div>

      <div className="min-h-[500px]">
        {step === 0 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">选择评审技能</h2>
            <p className="text-sm text-text-secondary mb-6">不同技能对应不同的评审视角和侧重点</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {SKILLS.map((skill) => (
                <button
                  key={skill.type}
                  onClick={() => setSelectedSkillType(skill.type)}
                  className={cn(
                    'flex flex-col p-5 rounded-xl border-2 transition-all cursor-pointer text-left',
                    'bg-bg-card hover:bg-bg-card-hover',
                    selectedSkillType === skill.type
                      ? `${skill.border} ${skill.bg}`
                      : 'border-border hover:border-border-hover'
                  )}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-brand-primary/20 bg-brand-primary/10">
                      <SkillIcon skill={skill} className="h-6 w-6" />
                    </span>
                    <div>
                      <h3 className={cn('font-bold font-display', skill.color)}>{skill.name}</h3>
                      <span className="text-xs text-text-muted font-mono">{skill.type}</span>
                    </div>
                  </div>
                  <p className="text-sm text-text-secondary leading-relaxed mb-3">{skill.description_zh}</p>
                  <div className="flex items-center gap-3 text-xs text-text-muted">
                    <span>{skill.task_types.length} 种任务</span>
                    <span>·</span>
                    <span>{skill.persona_count} 个角色</span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {skill.use_cases.slice(0, 3).map((uc) => (
                      <span key={uc} className="px-1.5 py-0.5 rounded text-[10px] bg-bg-secondary text-text-secondary">{uc}</span>
                    ))}
                  </div>
                </button>
              ))}
            </div>

            {selectedSkillType && (() => {
              const skill = SKILLS.find((s) => s.type === selectedSkillType)
              if (!skill) return null
              return (
                <div className={cn('mt-6 rounded-xl border p-4', skill.border, skill.bg)}>
                  <div className="flex items-center gap-2 mb-2">
                    <SkillIcon skill={skill} className="h-5 w-5" />
                    <span className={cn('font-medium text-sm', skill.color)}>{skill.name}</span>
                  </div>
                  <p className="text-sm text-text-secondary">{skill.description_zh}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {skill.task_types.map((tt) => {
                      const taskType = TASK_TYPES.find((t) => t.id === tt)
                      return taskType ? (
                        <span key={tt} className="px-2 py-0.5 rounded text-xs bg-bg-secondary text-text-secondary">
                          {taskType.icon} {taskType.name}
                        </span>
                      ) : null
                    })}
                  </div>
                </div>
              )
            })()}
          </div>
        )}

        {step === 1 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">选择任务类型</h2>
            <p className="text-sm text-text-secondary mb-6">
              {selectedSkillType
                ? `当前技能：${SKILLS.find((s) => s.type === selectedSkillType)?.name} · 以下为该技能支持的任务类型`
                : '选择你要评审的内容类型'}
            </p>

            <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2 scrollbar-hide -mx-4 px-4">
              <button
                onClick={() => setSelectedCategory('all')}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-lg font-display font-medium text-sm whitespace-nowrap transition-all duration-200',
                  selectedCategory === 'all'
                    ? 'bg-brand-primary/10 text-brand-primary border border-brand-primary/30'
                    : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
                )}
              >
                <span>全部</span>
                <span className={cn(
                  'px-1.5 py-0.5 rounded text-xs font-mono',
                  selectedCategory === 'all' ? 'bg-brand-primary/20 text-brand-primary' : 'bg-bg-secondary/50 text-text-muted'
                )}>
                  {filteredTaskTypes.length}
                </span>
              </button>

              {TASK_TYPE_CATEGORIES.map((category) => {
                const Icon = category.icon
                const count = filteredTaskTypes.filter((tt) => tt.category === category.id).length

                return (
                  <button
                    key={category.id}
                    onClick={() => setSelectedCategory(category.id)}
                    className={cn(
                      'flex items-center gap-2 px-4 py-2 rounded-lg font-display font-medium text-sm whitespace-nowrap transition-all duration-200',
                      selectedCategory === category.id
                        ? 'bg-brand-primary/10 text-brand-primary border border-brand-primary/30'
                        : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
                    )}
                  >
                    <Icon className="w-4 h-4" strokeWidth={1.25} />
                    <span>{category.name}</span>
                    <span className={cn(
                      'px-1.5 py-0.5 rounded text-xs font-mono',
                      selectedCategory === category.id ? 'bg-brand-primary/20 text-brand-primary' : 'bg-bg-secondary/50 text-text-muted'
                    )}>
                      {count}
                    </span>
                  </button>
                )
              })}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3">
              {filteredTaskTypes
                .filter((tt) => selectedCategory === 'all' || tt.category === selectedCategory)
                .map((tt) => (
                  <TaskTypeCard
                    key={tt.id}
                    taskType={tt}
                    selected={selectedTaskType === tt.id}
                    onClick={() => setSelectedTaskType(tt.id)}
                  />
                ))}
            </div>

            {selectedTaskType && (() => {
              const tt = TASK_TYPES.find((t) => t.id === selectedTaskType)
              if (!tt) return null
              return (
                <div className="mt-6 rounded-xl border border-border bg-bg-card p-4">
                  <h3 className="text-sm font-medium text-text-muted mb-3">评审模式</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {REVIEW_MODES.map((rm) => {
                      const mc = modeConfig[rm.mode]
                      return (
                        <button
                          key={rm.mode}
                          onClick={() => setSelectedMode(rm.mode)}
                          className={cn(
                            'flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all cursor-pointer text-left',
                            'bg-bg-card hover:bg-bg-card-hover',
                            selectedMode === rm.mode
                              ? `${mc.border} ${mc.bg}`
                              : 'border-border hover:border-border-hover'
                          )}
                        >
                          <div className="flex items-center gap-2 w-full">
                            <span className="text-lg">{mc.icon}</span>
                            <span className={cn(
                              'font-medium text-sm',
                              selectedMode === rm.mode ? mc.color : 'text-text-primary'
                            )}>
                              {mc.label}
                            </span>
                            <span className="ml-auto text-xs text-text-muted font-mono">
                              {rm.persona_count_range[0]}{rm.persona_count_range[0] !== rm.persona_count_range[1] ? `-${rm.persona_count_range[1]}` : ''} 人
                            </span>
                          </div>
                          <p className="text-xs text-text-secondary w-full">{rm.description}</p>
                          <div className="flex items-center gap-2 w-full text-xs text-text-muted">
                            {rm.cross_examination && <span className="px-1.5 py-0.5 rounded bg-cyan/10 text-cyan">交叉质询</span>}
                            {rm.calibration && <span className="px-1.5 py-0.5 rounded bg-warm-orange/10 text-warm-orange">校准检查</span>}
                            {!rm.cross_examination && !rm.calibration && <span className="text-text-muted/50">无额外步骤</span>}
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )
            })()}
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">上传评审材料</h2>
            <p className="text-sm text-text-secondary mb-6">手动填写文本，或上传文件让 AI 自动提取材料</p>

            <div className="flex items-center gap-2 mb-6">
              <button
                onClick={() => setMaterialInputMode('text')}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all',
                  materialInputMode === 'text'
                    ? 'bg-brand-primary/10 text-brand-primary border border-brand-primary/30'
                    : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
                )}
              >
                <AlignLeft className="w-4 h-4" strokeWidth={1.25} />
                文本输入
              </button>
              <button
                onClick={() => setMaterialInputMode('file')}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all',
                  materialInputMode === 'file'
                    ? 'bg-brand-primary/10 text-brand-primary border border-brand-primary/30'
                    : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
                )}
              >
                <FileText className="w-4 h-4" strokeWidth={1.25} />
                文件上传
              </button>
              {/* 这里曾经有第三个「目录路径」按钮，已下线——原因见文件顶部
                  MaterialInputMode 的注释（服务器扫不到客户端路径，且收上来的
                  directory_path 全仓无人读取）。 */}
            </div>

            {materialInputMode === 'file' && (
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onClick={() => !extracting && fileInputRef.current?.click()}
                className={cn(
                  'relative rounded-xl border-2 border-dashed p-6 md:p-8 text-center cursor-pointer transition-all mb-6',
                  extracting && 'pointer-events-none',
                  dragOver
                    ? 'border-brand-primary bg-brand-primary/5'
                    : 'border-border hover:border-brand-primary/30 hover:bg-bg-card'
                )}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.md,.json,.pdf,.docx"
                  multiple
                  onChange={handleFileInputChange}
                  className="hidden"
                />
                {extracting ? (
                  <div className="py-4">
                    <Loader2 className="w-8 h-8 mx-auto mb-3 text-brand-primary animate-spin" strokeWidth={1.25} />
                    <p className="text-sm text-brand-primary font-medium">AI 正在阅读文件并提取材料...</p>
                    <p className="text-xs text-text-muted mt-1">请稍候，通常需要 5-10 秒</p>
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 mx-auto mb-3 text-text-muted" strokeWidth={1.25} />
                    <p className="text-sm text-text-secondary">
                      拖拽文件到此处，或<span className="text-brand-primary">点击上传</span>
                    </p>
                    <p className="text-xs text-text-muted mt-1">
                      支持 .txt .md .json .pdf .docx（不支持旧版 .doc）· AI 自动提取结构化材料
                    </p>
                  </>
                )}
                {extractError && (
                  <p className="text-xs text-severity-critical mt-2">{extractError}</p>
                )}
                {filledMaterialsCount > 0 && !extracting && (
                  <p className="text-xs text-brand-primary mt-2">
                    已提取 {filledMaterialsCount} 个字段 · 可在下方编辑修改
                  </p>
                )}
              </div>
            )}

            {examples.length > 0 && (
              <div className="mb-6 rounded-xl border border-border bg-bg-card p-4">
                <button
                  onClick={() => setExamplesExpanded(!examplesExpanded)}
                  className="w-full flex items-center justify-between"
                >
                  <span className="flex items-center gap-2 text-sm font-medium text-text-secondary">
                    <Star className="w-4 h-4 text-brand-primary" strokeWidth={1.25} />
                    快速开始：导入示例数据
                  </span>
                  {examplesExpanded
                    ? <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                    : <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                  }
                </button>
                {examplesExpanded && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {examples.map((ex) => (
                      <button
                        key={ex.id}
                        onClick={() => handleImportExample(ex)}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-brand-primary/10 text-brand-primary hover:bg-brand-primary/20 transition-colors"
                      >
                        {ex.title}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="mb-6">
              <label className="block text-sm font-medium text-text-secondary mb-2">评审目标</label>
              <input
                type="text"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="例如：《星际漂流》概念设计文档"
                className="w-full px-4 py-3 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-brand-primary transition-colors"
              />
            </div>

            <div className="space-y-4 mb-6">
              <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 mb-3">
                <h3 className="text-sm font-medium text-text-secondary">编辑材料详情</h3>
                {filledMaterialsCount > 0 && (
                  <span className="text-xs text-brand-primary">AI 已提取 {filledMaterialsCount} 个字段，请检查并修改</span>
                )}
              </div>
              {currentFields.map((field, idx) => {
                const isFirstRequired = field.required && idx === currentFields.findIndex((f) => f.required)
                return (
                  <div key={field.key}>
                    <label className="flex items-center gap-1.5 text-sm font-medium text-text-secondary mb-1.5">
                      {field.label}
                      {field.required && <span className="text-severity-critical">*</span>}
                    </label>
                    {isFirstRequired ? (
                      <textarea
                        value={materialFields[field.key] ?? ''}
                        onChange={(e) => updateField(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        rows={5}
                        className="w-full px-4 py-3 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-brand-primary transition-colors resize-y"
                      />
                    ) : field.required ? (
                      <textarea
                        value={materialFields[field.key] ?? ''}
                        onChange={(e) => updateField(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        rows={3}
                        className="w-full px-4 py-3 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-brand-primary transition-colors resize-y"
                      />
                    ) : (
                      <input
                        type="text"
                        value={materialFields[field.key] ?? ''}
                        onChange={(e) => updateField(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        className="w-full px-4 py-2.5 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-brand-primary transition-colors"
                      />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">选择角色包</h2>
            <p className="text-sm text-text-secondary mb-6">选择一个角色包快速填充，或手动选择角色</p>

            <div className="mb-6 rounded-xl border border-border bg-bg-card p-4">
              <h3 className="text-sm font-medium text-text-muted mb-3">当前评审模式</h3>
              <div className="flex items-center gap-2">
                <span className="text-lg">{modeConfig[selectedMode].icon}</span>
                <span className={cn('font-medium text-sm', modeConfig[selectedMode].color)}>
                  {modeConfig[selectedMode].label}模式
                </span>
                <span className="text-xs text-text-muted">
                  · {currentModeConfig?.persona_count_range[0]}{currentModeConfig && currentModeConfig.persona_count_range[0] !== currentModeConfig.persona_count_range[1] ? `-${currentModeConfig.persona_count_range[1]}` : ''} 个角色
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              {packs.map((pack) => (
                <button
                  key={pack.panel_id}
                  onClick={() => {
                    if (selectedPack === pack.panel_id) {
                      // 取消选包时必须一起清空人格：以前只清 selectedPack，
                      // 整包角色仍留在 selectedPersonaIds 里，用户以为"取消了"，
                      // 实际带着一整包人继续往下走。
                      setSelectedPack(null)
                      setSelectedPersonaIds(new Set())
                      return
                    }
                    setSelectedPack(pack.panel_id)
                    // 只勾到模式上限为止：后端 select_panel_by_mode 无论如何都会
                    // selected[:max_count] 截断，整包全勾只会让界面显示一批实际
                    // 不会上场的人。截断顺序与后端一致（包内原顺序），用户看到的
                    // 就是真正会跑的那几位，想换人再手动改。
                    const packPersonas = personas.filter((p) => p.pack === pack.panel_id)
                    setSelectedPersonaIds(new Set(packPersonas.slice(0, modeMax).map((p) => p.id)))
                  }}
                  className={cn(
                    'flex flex-col items-center gap-2 p-3 md:p-4 rounded-xl border-2 transition-all cursor-pointer',
                    'bg-bg-card hover:bg-bg-card-hover',
                    selectedPack === pack.panel_id
                      ? 'border-brand-primary border-glow-green'
                      : 'border-border hover:border-border-hover'
                  )}
                >
                  <span className="text-2xl">{PACK_ICONS[pack.panel_id] ?? '📦'}</span>
                  <span className={cn(
                    'text-xs md:text-sm font-medium',
                    selectedPack === pack.panel_id ? 'text-brand-primary' : 'text-text-primary'
                  )}>
                    {pack.name}
                  </span>
                  <span className="text-xs text-text-muted">{pack.persona_count} 个角色</span>
                </button>
              ))}
            </div>

            {selectedPack && (() => {
              const pack = packs.find((p) => p.panel_id === selectedPack)
              if (!pack) return null
              return (
                <div className="mb-8 px-4 py-3 rounded-lg bg-brand-primary/5 border border-brand-primary/20">
                  <p className="text-sm text-text-secondary">
                    <span className="text-brand-primary font-medium">{pack.name}</span>：{pack.description}
                  </p>
                </div>
              )
            })()}

            <h3 className="text-lg font-semibold text-text-primary mb-4">
              角色列表
              <span className="text-sm font-normal text-text-muted ml-2">
                已选择 {selectedPersonaIds.size} / 上限 {modeMax} 个
              </span>
            </h3>

            {/* 会被后端静默改写的组合，在这里就说清楚，而不是等报告出来人对不上 */}
            {packConflict && (
              <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-severity-critical/40 bg-severity-critical/5 p-3">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-severity-critical" strokeWidth={1.5} />
                <div className="text-xs text-text-secondary leading-relaxed">
                  <p className="text-severity-critical font-medium mb-1">
                    不能跨角色包混选（当前混了 {selectedPackIds.length} 个包：
                    {selectedPackIds.map(packName).join('、')}）
                  </p>
                  <p>
                    一次评审只能使用同一个角色包内的角色，跨包选择时只会保留其中一个包。
                    请只保留同一包内的角色，或直接点上面的角色包一键选择。
                  </p>
                </div>
              </div>
            )}
            {!packConflict && overModeMax && (
              <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-warm-orange/40 bg-warm-orange/5 p-3">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.5} />
                <div className="text-xs text-text-secondary leading-relaxed">
                  <p className="text-warm-orange font-medium mb-1">
                    超出「{modeConfig[selectedMode].label}模式」的角色上限（{modeMax} 位）
                  </p>
                  <p>
                    当前模式最多支持 {modeMax} 位评审员，请取消 {selectedPersonaIds.size - modeMax} 位，
                    或回到「任务类型」步骤选择人数上限更高的模式。
                  </p>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredPersonas.map((persona) => (
                <PersonaSelectCard
                  key={persona.id}
                  persona={persona}
                  selected={selectedPersonaIds.has(persona.id)}
                  // 未选包时列表是全部包混在一起的，不标出归属就没法自己避开跨包混选
                  packLabel={selectedPack ? null : packName(persona.pack ?? 'game-core')}
                  onToggle={() => togglePersona(persona.id)}
                />
              ))}
            </div>
          </div>
        )}

        {step === 4 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">评审选项</h2>
            <p className="text-sm text-text-secondary mb-6">配置评审的附加功能</p>

            <div className="space-y-4">
              <button
                onClick={() => setEnableEvaluation(!enableEvaluation)}
                className={cn(
                  'w-full flex items-start gap-4 p-5 rounded-xl border-2 transition-all cursor-pointer text-left',
                  'bg-bg-card hover:bg-bg-card-hover',
                  enableEvaluation
                    ? 'border-cyan/50 bg-cyan/5'
                    : 'border-border'
                )}
              >
                <div className={cn(
                  'w-5 h-5 rounded border-2 shrink-0 mt-0.5 flex items-center justify-center transition-all',
                  enableEvaluation ? 'bg-cyan border-cyan' : 'border-border'
                )}>
                  {enableEvaluation && <CheckCircle2 className="w-3 h-3 text-white" strokeWidth={1.25} />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <FlaskConical className="w-4 h-4 text-cyan" strokeWidth={1.25} />
                    <span className={cn('font-medium text-sm', enableEvaluation ? 'text-cyan' : 'text-text-primary')}>
                      启用评估报告
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    评审完成后自动运行 8 维度评估，生成评分卡和伦理报告。评估覆盖覆盖度、深度、一致性、可行动性、证据质量、偏见检测、新颖性、伦理安全等维度。
                  </p>
                  {enableEvaluation && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {['覆盖度', '深度', '一致性', '可行动性', '证据质量', '偏见检测', '新颖性', '伦理安全'].map((d) => (
                        <span key={d} className="px-2 py-0.5 rounded text-xs bg-cyan/10 text-cyan">{d}</span>
                      ))}
                    </div>
                  )}
                </div>
              </button>

              <button
                onClick={() => setEnableRedTeam(!enableRedTeam)}
                className={cn(
                  'w-full flex items-start gap-4 p-5 rounded-xl border-2 transition-all cursor-pointer text-left',
                  'bg-bg-card hover:bg-bg-card-hover',
                  enableRedTeam
                    ? 'border-red-400/50 bg-red-400/5'
                    : 'border-border'
                )}
              >
                <div className={cn(
                  'w-5 h-5 rounded border-2 shrink-0 mt-0.5 flex items-center justify-center transition-all',
                  enableRedTeam ? 'bg-red-400 border-red-400' : 'border-border'
                )}>
                  {enableRedTeam && <CheckCircle2 className="w-3 h-3 text-white" strokeWidth={1.25} />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Shield className="w-4 h-4 text-red-400" strokeWidth={1.25} />
                    <span className={cn('font-medium text-sm', enableRedTeam ? 'text-red-400' : 'text-text-primary')}>
                      启用红队对抗
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    标准评审完成后，自动启动红队对抗模式，用对抗性视角主动攻击产品弱点，模拟最挑剔的用户和恶意场景，暴露隐藏风险。
                  </p>
                  {enableRedTeam && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {['付费模型压力测试', '社区危机预演', '本地化文化风险', '公关危机模拟'].map((uc) => (
                        <span key={uc} className="px-2 py-0.5 rounded text-xs bg-red-400/10 text-red-400">{uc}</span>
                      ))}
                    </div>
                  )}
                </div>
              </button>
            </div>
          </div>
        )}

        {step === 5 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">确认评审配置</h2>
            <p className="text-sm text-text-secondary mb-6">检查以下信息，确认无误后启动评审</p>

            <div className="space-y-3">
              {selectedSkillType && (() => {
                const skill = SKILLS.find((s) => s.type === selectedSkillType)
                if (!skill) return null
                return (
                  <div className={cn('rounded-xl border p-4 md:p-5', skill.border, skill.bg)}>
                    <h3 className="text-sm font-medium text-text-muted mb-2">评审技能</h3>
                    <div className="flex items-center gap-2">
                      <SkillIcon skill={skill} className="h-5 w-5" />
                      <span className={cn('font-medium text-sm', skill.color)}>{skill.name}</span>
                    </div>
                  </div>
                )
              })()}

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <h3 className="text-sm font-medium text-text-muted mb-2">任务类型</h3>
                {(() => {
                  const tt = TASK_TYPES.find((t) => t.id === selectedTaskType)
                  if (!tt) return null
                  const Icon = tt.IconComponent
                  return (
                    <p className="text-text-primary flex items-center gap-2">
                      <Icon className="w-5 h-5 text-brand-primary" strokeWidth={1.25} />
                      {tt.name}
                    </p>
                  )
                })()}
              </div>

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <h3 className="text-sm font-medium text-text-muted mb-2">评审模式</h3>
                <div className="flex items-center gap-2">
                  <span className="text-lg">{modeConfig[selectedMode].icon}</span>
                  <span className={cn('font-medium text-sm', modeConfig[selectedMode].color)}>
                    {modeConfig[selectedMode].label}模式
                  </span>
                  <span className="text-xs text-text-muted">
                    · {currentModeConfig?.description}
                  </span>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <h3 className="text-sm font-medium text-text-muted mb-2">评审目标</h3>
                <p className="text-text-primary">{target || '未填写'}</p>
              </div>

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <button
                  onClick={() => setMaterialsExpanded(!materialsExpanded)}
                  className="w-full flex items-center justify-between"
                >
                  <h3 className="text-sm font-medium text-text-muted">
                    评审材料
                    <span className="ml-2 text-brand-primary">{filledMaterialsCount}</span>
                    <span className="text-text-muted"> / {currentFields.length} 项已填写</span>
                  </h3>
                  {materialsExpanded
                    ? <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                    : <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                  }
                </button>
                {materialsExpanded && (
                  <div className="mt-3 space-y-2">
                    {currentFields.map((field) => {
                      const value = materialFields[field.key]
                      if (!value || value.trim() === '') {
                        return (
                          <div key={field.key} className="flex items-start gap-2 text-sm">
                            <span className="text-text-muted shrink-0">{field.label}：</span>
                            <span className="text-text-muted/50 italic">未填写</span>
                          </div>
                        )
                      }
                      return (
                        <div key={field.key} className="flex items-start gap-2 text-sm">
                          <span className="text-text-secondary shrink-0">{field.label}：</span>
                          <span className="text-text-primary line-clamp-3">{value}</span>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                {/* 把真正提交的角色包一起摆出来：报告里出现的就是这个包里的这几位，
                    不再有"确认页显示 A、报告里跑的是 B"的落差 */}
                <h3 className="text-sm font-medium text-text-muted mb-2">
                  已选角色 ({selectedPersonas.length})
                  {effectivePack && (
                    <span className="ml-2 font-normal text-text-muted/80">· 角色包：{packName(effectivePack)}</span>
                  )}
                </h3>
                <div className="flex flex-wrap gap-2">
                  {selectedPersonas.map((p) => (
                    <span
                      key={p.id}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-brand-primary/10 text-brand-primary text-xs"
                    >
                      {p.name}
                      <button
                        onClick={() => togglePersona(p.id)}
                        className="hover:text-severity-critical transition-colors"
                      >
                        <X className="w-3 h-3" strokeWidth={1.25} />
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              {(enableEvaluation || enableRedTeam) && (
                <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                  <h3 className="text-sm font-medium text-text-muted mb-2">附加功能</h3>
                  <div className="flex flex-wrap gap-2">
                    {enableEvaluation && (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-cyan/10 text-cyan text-xs">
                        <FlaskConical className="w-3 h-3" strokeWidth={1.25} />
                        评估报告
                      </span>
                    )}
                    {enableRedTeam && (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-red-400/10 text-red-400 text-xs">
                        <Shield className="w-3 h-3" strokeWidth={1.25} />
                        红队对抗
                      </span>
                    )}
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <h3 className="text-sm font-medium text-text-muted mb-2">预估成本</h3>
                {(() => {
                  const baseCostMap: Record<string, number> = {
                    concept_review: 0.06,
                    demo_first_play: 0.10,
                    steam_page_review: 0.08,
                    kickstarter_review: 0.09,
                    discord_community_review: 0.07,
                    devlog_review: 0.05,
                    monetization_review: 0.08,
                    update_announcement_review: 0.06,
                    localization_review: 0.07,
                    looking_for_party_post: 0.04,
                    app_store_review: 0.08,
                    social_media_post: 0.06,
                    video_ad_review: 0.07,
                    landing_page_review: 0.07,
                  }
                  const baseCost = baseCostMap[selectedTaskType ?? ''] ?? 0.08
                  const totalCost = selectedPersonas.length * baseCost
                  const evalCost = enableEvaluation ? 0.05 : 0
                  const redTeamCost = enableRedTeam ? 0.08 : 0
                  const finalCost = totalCost + evalCost + redTeamCost
                  const taskName = TASK_TYPES.find((t) => t.id === selectedTaskType)?.name ?? selectedTaskType
                  return (
                    <>
                      <p className="font-display text-brand-primary text-lg">
                        ${finalCost.toFixed(2)}
                      </p>
                      <p className="text-xs text-text-muted mt-1">
                        {selectedPersonas.length} 个角色 × ${baseCost.toFixed(2)}/角色（{taskName}）
                        {enableEvaluation && ` + $${evalCost.toFixed(2)} 评估`}
                        {enableRedTeam && ` + $${redTeamCost.toFixed(2)} 红队`}
                      </p>
                    </>
                  )
                })()}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-8 pt-6 border-t border-border">
        <button
          onClick={handlePrev}
          disabled={step === 0}
          className={cn(
            'flex items-center gap-2 px-4 md:px-5 py-2.5 rounded-lg font-medium transition-all text-sm',
            step === 0
              ? 'text-text-muted cursor-not-allowed'
              : 'text-text-secondary hover:text-text-primary hover:bg-bg-card'
          )}
        >
          <ArrowLeft className="w-4 h-4" strokeWidth={1.25} />
          上一步
        </button>

        {step < 5 ? (
          <button
            onClick={handleNext}
            disabled={!canNext()}
            className={cn(
              'flex items-center gap-2 px-5 md:px-6 py-2.5 rounded-lg font-medium transition-all text-sm',
              canNext()
                ? 'bg-brand-primary text-white hover:bg-brand-primary-dim hover:shadow-[0_4px_16px_rgba(0,113,227,0.30)]'
                : 'bg-bg-card text-text-muted cursor-not-allowed'
            )}
          >
            下一步
            <ArrowRight className="w-4 h-4" strokeWidth={1.25} />
          </button>
        ) : (
          <div className="flex items-center gap-3">
            {launchError && (
              <p className="max-w-md text-sm text-severity-critical">{launchError}</p>
            )}
            <button
              onClick={handleLaunch}
              disabled={launching}
              className={cn(
                'flex items-center gap-2 px-6 md:px-8 py-2.5 rounded-lg bg-brand-primary text-white font-bold hover:bg-brand-primary-dim glow-green transition-all text-sm',
                launching && 'opacity-70 cursor-not-allowed'
              )}
            >
              {launching ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} /> : '🚀 启动评审'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function PersonaSelectCard({
  persona,
  selected,
  packLabel,
  onToggle,
}: {
  persona: Persona
  selected: boolean
  /** 未选包、列表混着全部包时显示归属包名；选了包就是冗余信息，传 null */
  packLabel: string | null
  onToggle: () => void
}) {
  return (
    <div
      onClick={onToggle}
      className={cn(
        'flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all',
        'bg-bg-card hover:bg-bg-card-hover',
        selected ? 'border-brand-primary/50' : 'border-border'
      )}
    >
      <div className={cn(
        'w-5 h-5 rounded border-2 shrink-0 mt-0.5 flex items-center justify-center transition-all',
        selected ? 'bg-brand-primary border-brand-primary' : 'border-border'
      )}>
        {selected && <CheckCircle2 className="w-3 h-3 text-white" strokeWidth={1.25} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary">{persona.name}</span>
          <span className="text-xs text-text-muted">{persona.archetype}</span>
          {packLabel && (
            <span className="shrink-0 rounded bg-bg-secondary px-1.5 py-0.5 text-[10px] text-text-muted">
              {packLabel}
            </span>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-0.5 line-clamp-1">{persona.identity_summary}</p>
      </div>
      <div className="shrink-0 hidden sm:block">
        <PersonaRadarChart data={persona.behavior_profile} size={60} mobileSize={48} />
      </div>
    </div>
  )
}
