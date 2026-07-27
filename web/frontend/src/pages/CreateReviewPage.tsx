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
import { ArrowLeft, ArrowRight, Upload, CheckCircle2, X, Loader2, ChevronDown, ChevronUp, Star, FolderOpen, AlignLeft, FileText, Shield, FlaskConical } from 'lucide-react'

type Step = 0 | 1 | 2 | 3 | 4 | 5
type MaterialInputMode = 'text' | 'file' | 'directory'

const modeConfig: Record<ReviewMode, { label: string; color: string; bg: string; border: string; icon: string }> = {
  quick: { label: '快速', color: 'text-cyan', bg: 'bg-cyan/10', border: 'border-cyan/30', icon: '⚡' },
  standard: { label: '标准', color: 'text-neon-green', bg: 'bg-neon-green/10', border: 'border-neon-green/30', icon: '✅' },
  full: { label: '完整', color: 'text-warm-orange', bg: 'bg-warm-orange/10', border: 'border-warm-orange/30', icon: '🔬' },
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
  const [directoryPath, setDirectoryPath] = useState('')
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
      if (materialInputMode === 'directory' && directoryPath.trim() === '') return false
      return requiredFields.every((f) => (materialFields[f.key] ?? '').trim() !== '')
    }
    if (step === 3) return selectedPersonaIds.size > 0
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

      if (materialInputMode === 'directory' && directoryPath.trim()) {
        artifactBundle.directory_path = directoryPath.trim()
      }

      // 走 v2 异步链路（Job 队列 + WS 进度）。此前走 v1 同步接口：阻塞线程池、
      // 无视 BYOK key、无 key 时把模拟数据当真实报告入库——三个坑一次躲掉。
      const reviewId = await createNewReview({
        task_type: selectedTaskType,
        artifact_bundle: artifactBundle,
        persona_pack: selectedPack ?? undefined,
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

  const selectedPersonas = personas.filter((p) => selectedPersonaIds.has(p.id))

  const filledMaterialsCount = Object.entries(materialFields).filter(([, v]) => v.trim() !== '').length

  const currentModeConfig = REVIEW_MODES.find((m) => m.mode === selectedMode)

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 animate-fade-in">
      <div className="flex items-center gap-2 md:gap-4 mb-8">
        {Array.from({ length: 6 }, (_, i) => i).map((s) => (
          <div key={s} className="flex items-center gap-1 md:gap-2 flex-1">
            <div
              className={cn(
                'w-7 h-7 md:w-8 md:h-8 rounded-full flex items-center justify-center text-xs md:text-sm font-mono font-bold shrink-0 transition-all',
                s < step
                  ? 'bg-neon-green text-bg-primary'
                  : s === step
                    ? 'bg-neon-green/20 text-neon-green border-2 border-neon-green'
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
                s < step ? 'bg-gradient-to-r from-neon-green/60 to-neon-green' : 'bg-border'
              )} />
            )}
          </div>
        ))}
      </div>

      <div className="min-h-[500px]">
        {step === 0 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">选择评审技能</h2>
            <p className="text-sm text-text-secondary mb-6">不同技能提供差异化的评审策略，选择最适合你当前需求的技能</p>

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
                    <span className="text-2xl">{skill.icon}</span>
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
                    <span className="text-lg">{skill.icon}</span>
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
                    ? 'bg-neon-green/10 text-neon-green border border-neon-green/30'
                    : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
                )}
              >
                <span>全部</span>
                <span className={cn(
                  'px-1.5 py-0.5 rounded text-xs font-mono',
                  selectedCategory === 'all' ? 'bg-neon-green/20 text-neon-green' : 'bg-bg-secondary/50 text-text-muted'
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
            <p className="text-sm text-text-secondary mb-6">通过文本输入、文件上传或目录路径提供评审材料</p>

            <div className="flex items-center gap-2 mb-6">
              <button
                onClick={() => setMaterialInputMode('text')}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all',
                  materialInputMode === 'text'
                    ? 'bg-neon-green/10 text-neon-green border border-neon-green/30'
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
                    ? 'bg-neon-green/10 text-neon-green border border-neon-green/30'
                    : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
                )}
              >
                <FileText className="w-4 h-4" strokeWidth={1.25} />
                文件上传
              </button>
              <button
                onClick={() => setMaterialInputMode('directory')}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all',
                  materialInputMode === 'directory'
                    ? 'bg-neon-green/10 text-neon-green border border-neon-green/30'
                    : 'bg-bg-card border border-border text-text-secondary hover:border-cyan/30'
                )}
              >
                <FolderOpen className="w-4 h-4" strokeWidth={1.25} />
                目录路径
              </button>
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
                    ? 'border-neon-green bg-neon-green/5'
                    : 'border-border hover:border-neon-green/30 hover:bg-bg-card'
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
                    <Loader2 className="w-8 h-8 mx-auto mb-3 text-neon-green animate-spin" strokeWidth={1.25} />
                    <p className="text-sm text-neon-green font-medium">AI 正在阅读文件并提取材料...</p>
                    <p className="text-xs text-text-muted mt-1">请稍候，通常需要 5-10 秒</p>
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 mx-auto mb-3 text-text-muted" strokeWidth={1.25} />
                    <p className="text-sm text-text-secondary">
                      拖拽文件到此处，或<span className="text-neon-green">点击上传</span>
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
                  <p className="text-xs text-neon-green mt-2">
                    已提取 {filledMaterialsCount} 个字段 · 可在下方编辑修改
                  </p>
                )}
              </div>
            )}

            {materialInputMode === 'directory' && (
              <div className="mb-6 rounded-xl border border-border bg-bg-card p-4">
                <label className="block text-sm font-medium text-text-secondary mb-2">项目目录路径</label>
                <input
                  type="text"
                  value={directoryPath}
                  onChange={(e) => setDirectoryPath(e.target.value)}
                  placeholder="例如：/path/to/your/game/project 或 C:\Projects\MyGame"
                  className="w-full px-4 py-3 rounded-lg bg-bg-secondary border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors font-mono text-sm"
                />
                <p className="text-xs text-text-muted mt-2">
                  输入项目目录路径，系统将自动扫描目录中的文件并提取评审材料
                </p>
              </div>
            )}

            {examples.length > 0 && (
              <div className="mb-6 rounded-xl border border-border bg-bg-card p-4">
                <button
                  onClick={() => setExamplesExpanded(!examplesExpanded)}
                  className="w-full flex items-center justify-between"
                >
                  <span className="flex items-center gap-2 text-sm font-medium text-text-secondary">
                    <Star className="w-4 h-4 text-neon-green" strokeWidth={1.25} />
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
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-neon-green/10 text-neon-green hover:bg-neon-green/20 transition-colors"
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
                className="w-full px-4 py-3 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors"
              />
            </div>

            <div className="space-y-4 mb-6">
              <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 mb-3">
                <h3 className="text-sm font-medium text-text-secondary">编辑材料详情</h3>
                {filledMaterialsCount > 0 && (
                  <span className="text-xs text-neon-green">AI 已提取 {filledMaterialsCount} 个字段，请检查并修改</span>
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
                        className="w-full px-4 py-3 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors resize-y"
                      />
                    ) : field.required ? (
                      <textarea
                        value={materialFields[field.key] ?? ''}
                        onChange={(e) => updateField(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        rows={3}
                        className="w-full px-4 py-3 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors resize-y"
                      />
                    ) : (
                      <input
                        type="text"
                        value={materialFields[field.key] ?? ''}
                        onChange={(e) => updateField(field.key, e.target.value)}
                        placeholder={field.placeholder}
                        className="w-full px-4 py-2.5 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-neon-green transition-colors"
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
                    setSelectedPack(selectedPack === pack.panel_id ? null : pack.panel_id)
                    if (selectedPack !== pack.panel_id) {
                      const packPersonas = personas.filter((p) => p.pack === pack.panel_id)
                      setSelectedPersonaIds(new Set(packPersonas.map((p) => p.id)))
                    }
                  }}
                  className={cn(
                    'flex flex-col items-center gap-2 p-3 md:p-4 rounded-xl border-2 transition-all cursor-pointer',
                    'bg-bg-card hover:bg-bg-card-hover',
                    selectedPack === pack.panel_id
                      ? 'border-neon-green border-glow-green'
                      : 'border-border hover:border-border-hover'
                  )}
                >
                  <span className="text-2xl">{PACK_ICONS[pack.panel_id] ?? '📦'}</span>
                  <span className={cn(
                    'text-xs md:text-sm font-medium',
                    selectedPack === pack.panel_id ? 'text-neon-green' : 'text-text-primary'
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
                <div className="mb-8 px-4 py-3 rounded-lg bg-neon-green/5 border border-neon-green/20">
                  <p className="text-sm text-text-secondary">
                    <span className="text-neon-green font-medium">{pack.name}</span>：{pack.description}
                  </p>
                </div>
              )
            })()}

            <h3 className="text-lg font-semibold text-text-primary mb-4">
              角色列表
              <span className="text-sm font-normal text-text-muted ml-2">
                已选择 {selectedPersonaIds.size} 个
              </span>
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredPersonas.map((persona) => (
                <PersonaSelectCard
                  key={persona.id}
                  persona={persona}
                  selected={selectedPersonaIds.has(persona.id)}
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
                  {enableEvaluation && <CheckCircle2 className="w-3 h-3 text-bg-primary" strokeWidth={1.25} />}
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
                  {enableRedTeam && <CheckCircle2 className="w-3 h-3 text-bg-primary" strokeWidth={1.25} />}
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
                      <span className="text-lg">{skill.icon}</span>
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
                      <Icon className="w-5 h-5 text-neon-green" strokeWidth={1.25} />
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

              {materialInputMode === 'directory' && directoryPath.trim() && (
                <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                  <h3 className="text-sm font-medium text-text-muted mb-2">目录路径</h3>
                  <p className="text-text-primary font-mono text-sm">{directoryPath}</p>
                </div>
              )}

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <button
                  onClick={() => setMaterialsExpanded(!materialsExpanded)}
                  className="w-full flex items-center justify-between"
                >
                  <h3 className="text-sm font-medium text-text-muted">
                    评审材料
                    <span className="ml-2 text-neon-green">{filledMaterialsCount}</span>
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
                <h3 className="text-sm font-medium text-text-muted mb-2">已选角色 ({selectedPersonas.length})</h3>
                <div className="flex flex-wrap gap-2">
                  {selectedPersonas.map((p) => (
                    <span
                      key={p.id}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-neon-green/10 text-neon-green text-xs"
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
                      <p className="font-display text-neon-green text-lg">
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
                ? 'bg-neon-green text-bg-primary hover:bg-neon-green-dim hover:shadow-[0_0_20px_rgba(183,126,59,0.25)]'
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
                'flex items-center gap-2 px-6 md:px-8 py-2.5 rounded-lg bg-neon-green text-bg-primary font-bold hover:bg-neon-green-dim glow-green transition-all text-sm',
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

function PersonaSelectCard({ persona, selected, onToggle }: { persona: Persona; selected: boolean; onToggle: () => void }) {
  return (
    <div
      onClick={onToggle}
      className={cn(
        'flex items-start gap-3 p-3 rounded-lg border-2 cursor-pointer transition-all',
        'bg-bg-card hover:bg-bg-card-hover',
        selected ? 'border-neon-green/50' : 'border-border'
      )}
    >
      <div className={cn(
        'w-5 h-5 rounded border-2 shrink-0 mt-0.5 flex items-center justify-center transition-all',
        selected ? 'bg-neon-green border-neon-green' : 'border-border'
      )}>
        {selected && <CheckCircle2 className="w-3 h-3 text-bg-primary" strokeWidth={1.25} />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-text-primary">{persona.name}</span>
          <span className="text-xs text-text-muted">{persona.archetype}</span>
        </div>
        <p className="text-xs text-text-secondary mt-0.5 line-clamp-1">{persona.identity_summary}</p>
      </div>
      <div className="shrink-0 hidden sm:block">
        <PersonaRadarChart data={persona.behavior_profile} size={60} mobileSize={48} />
      </div>
    </div>
  )
}
