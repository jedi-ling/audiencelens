import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { cn } from '@/lib/utils'
import { TASK_TYPES, PACK_ICONS, TASK_MATERIALS, TASK_TYPE_CATEGORIES, REVIEW_MODES, EVALUATION_DIMENSIONS } from '@/lib/mock-data'
import type { Persona, TaskMaterialField, Example, ReviewMode, SkillType } from '@/lib/mock-data'
import { extractMaterials } from '@/lib/api'
import { usePersonaStore } from '@/store/persona-store'
import { useReviewStore } from '@/store/review-store'
import { loadSkillTruth, NON_REVIEW_SKILL_TYPES } from '@/lib/skills'
import type { SkillTruth } from '@/lib/skills'
import TaskTypeCard from '@/components/TaskTypeCard'
import PersonaRadarChart from '@/components/PersonaRadarChart'
import { ArrowLeft, ArrowRight, Upload, CheckCircle2, X, Loader2, ChevronDown, ChevronUp, Star, AlignLeft, FileText, Shield, FlaskConical, AlertTriangle, RefreshCw } from 'lucide-react'

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
 *
 * deco 可能缺席（后端新增了技能而前端还没配图），此时不画图标而不是画一张碎图。
 */
function SkillIcon({ skill, className }: { skill: SkillTruth; className?: string }) {
  if (!skill.deco) return null
  return (
    <img
      src={skill.deco.icon}
      alt=""
      className={cn('object-contain', className)}
      loading="lazy"
    />
  )
}

/**
 * 任务类型在 TASK_MATERIALS 里没有字段定义时的兜底。
 *
 * 曾经的表现是：currentFields 落到 `?? []`，第 2 步渲染成一个输入框都没有的空页，
 * requiredFields 为空又让 canNext() 只校验标题非空——用户只填一句标题就能一路启动，
 * 拿回一份基于一句话生成的报告，还以为自己填完了。mock-data 那边已经把 4 个漏掉的
 * 任务类型补齐，但那是「这次补上了」，不是「以后不会再漏」：新增任务类型时同样会漏。
 * 所以这里留一道结构性兜底，宁可问一个笼统的问题，也不能让人交白卷。
 */
const GENERIC_MATERIAL_FIELD: TaskMaterialField = {
  key: '材料正文',
  label: '材料正文',
  placeholder: '粘贴要评审的材料全文（这个任务类型还没有配置分项字段，先整段贴进来）...',
  required: true,
}

export default function CreateReviewPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  // 技能 id 是后端的字符串，不做 `as SkillType` 断言：断言只是让类型检查闭嘴，
  // 并不能让一个后端新增的技能真的属于这个前端联合类型（同 SkillSelectPage 的口径）。
  const requestedSkill = searchParams.get('skill')
  // 不接受不能创建评审的技能（如 persona_generate）：老链接/收藏夹还会带着它进来，
  // 照单全收就等于把刚关掉的那个假入口从后门放回来。
  const preselectedSkill =
    requestedSkill && !NON_REVIEW_SKILL_TYPES.includes(requestedSkill) ? requestedSkill : null
  const droppedSkill = requestedSkill && !preselectedSkill ? requestedSkill : null
  const requestedTask = searchParams.get('task')
  const preselectedTask = TASK_TYPES.some((task) => task.id === requestedTask) ? requestedTask : null
  // 这里曾经用本地 SKILLS[].task_types 反推「这个任务类型属于哪个技能」。那份映射
  // 在后端不存在（skill_type × task_type 零校验），推出来的技能是猜的，却会被当成
  // 用户的选择提交上去。猜不出来就不猜：技能留空，用户想选自己回第 0 步选。
  const [step, setStep] = useState<Step>(preselectedTask ? 2 : preselectedSkill ? 1 : 0)
  const [selectedSkillType, setSelectedSkillType] = useState<string | null>(preselectedSkill)
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
  // 技能清单以 /api/skills 为唯一事实源。以前第 0 步的名称/描述读的是本地 SKILLS，
  // 后端改了文案这一页不会跟，同一个技能在技能中心和创建页会显示两种说法。
  const [skills, setSkills] = useState<SkillTruth[] | null>(null)
  const [skillsError, setSkillsError] = useState<string | null>(null)
  const [skillsLoading, setSkillsLoading] = useState(true)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { personas, packs, initPersonas, initialized } = usePersonaStore()
  const { examples, fetchExamplesList, createNewReview } = useReviewStore()

  useEffect(() => {
    if (!initialized) initPersonas()
  }, [initialized, initPersonas])

  useEffect(() => {
    fetchExamplesList()
  }, [fetchExamplesList])

  const loadSkills = useCallback(() => {
    setSkillsLoading(true)
    setSkillsError(null)
    loadSkillTruth()
      .then((list) => {
        // 摘掉不能创建评审的技能：这一页的每张卡都通向「发起评审」，
        // 放一个点了不改变任何行为的技能进来就是在卖一个不存在的东西。
        setSkills(list.filter((s) => !NON_REVIEW_SKILL_TYPES.includes(s.type)))
        setSkillsLoading(false)
      })
      .catch((e: unknown) => {
        // 不回落本地 SKILLS：那份清单可能已经和后端不一致，拿它假装加载成功，
        // 用户会挑一个后端根本没有的技能。取不到就说取不到。
        setSkills(null)
        setSkillsError(e instanceof Error ? e.message : '加载技能列表失败')
        setSkillsLoading(false)
      })
  }, [])

  useEffect(() => {
    loadSkills()
  }, [loadSkills])

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

  const selectedSkill = skills?.find((s) => s.type === selectedSkillType) ?? null

  const definedFields: TaskMaterialField[] = selectedTaskType
    ? TASK_MATERIALS[selectedTaskType] ?? []
    : []
  /** 真正渲染与校验用的字段。没有定义时退回一个必填的通用正文框，见 GENERIC_MATERIAL_FIELD。 */
  const currentFields: TaskMaterialField[] =
    selectedTaskType && definedFields.length === 0 ? [GENERIC_MATERIAL_FIELD] : definedFields

  /**
   * AI 从上传文件里提取出来、但不在 currentFields 里的键。
   *
   * handleFileUpload 把 /api/extract-materials 返回的键全部写进 materialFields，
   * 提交时也全量提交，但界面只按 currentFields 渲染——后端多提取出一个键，
   * 那段内容就会被悄悄发给评审引擎，用户在页面上看不见、改不了、删不掉。
   * 这里把它们一并列出来，用户至少知道自己交了什么。
   */
  const extraFieldKeys = Object.keys(materialFields).filter(
    (k) => !currentFields.some((f) => f.key === k) && (materialFields[k] ?? '').trim() !== ''
  )

  /**
   * 任务类型列表只按后端声明的 task_types 过滤。
   *
   * 这里以前用本地 SKILLS[].task_types 裁选项，而后端对 skill_type × task_type
   * 的组合没有任何校验——等于前端凭空造了一条约束，把用户想选的类型藏起来，
   * 用户会以为「这个技能不支持我要评的东西」而放弃。
   * taskTypes 为 null 表示后端没对这个技能声明任务类型（不是「一个都不支持」），
   * 这种情况下不裁：宁可多给选项，也不能替后端发明限制。
   */
  const skillTaskTypes = selectedSkill?.taskTypes ?? null
  const filteredTaskTypes = skillTaskTypes
    ? TASK_TYPES.filter((tt) => skillTaskTypes.includes(tt.id))
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
      if (!requiredFields.every((f) => (materialFields[f.key] ?? '').trim() !== '')) return false
      // 最后一道：一份材料都没有的评审不该发得出去。requiredFields 现在恒不为空
      // （没有字段定义时会退到 GENERIC_MATERIAL_FIELD），但将来若有人把某个任务类型的
      // 字段全设成选填，这里仍然拦得住——只填标题就启动，跑出来的是一份基于一句话的报告。
      return Object.values(materialFields).some((v) => v.trim() !== '')
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
    const materials = Object.entries(materialFields)
      .filter(([, value]) => value.trim() !== '')
      .map(([type, description]) => ({ type, description }))
    // 空材料的评审不发出去：引擎只能拿标题当全部输入，跑出来是一份看着正常
    // 却什么都没读过的报告，用户没法从结果里看出自己漏交了东西。
    if (materials.length === 0) {
      setLaunchError('还没有填写任何评审材料，请返回第 2 步补充后再启动')
      setStep(2)
      return
    }
    setLaunching(true)
    setLaunchError(null)
    try {

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
        // review-store 把 skill_type 声明成前端联合类型 SkillType，而这个值来自后端
        // /api/skills（后端新增技能时它可以是联合里没有的字符串）。这里只是原样透传，
        // 不做校验，断言只是为了穿过那个过窄的类型——正解是 review-store 改成 string。
        skill_type: (selectedSkillType ?? undefined) as SkillType | undefined,
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
    } catch (e) {
      // 原因必须如实透出：后端会告诉你是文件太大、格式不支持、没配 API key、限流还是
      // 鉴权失败，这些用户改一下就能过。一律替换成「AI 提取失败」，用户会以为是模型不行，
      // 于是放弃这个功能。后半句保留手填这条退路。
      const reason = e instanceof Error && e.message ? e.message : '未知原因'
      setExtractError(`AI 提取失败：${reason}。你也可以直接手动填写下面的材料字段。`)
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
      <div
      // 表单列收窄为 3xl 并居中：多步表单是阅读+填写型内容，超宽屏上
      // 拉满会让标签和输入框的视线跨距过长、卡片网格变得稀疏
      className="max-w-3xl mx-auto px-4 py-8 animate-fade-in overflow-x-hidden"
      >
      <div className="flex items-center gap-2 md:gap-4 mb-8">
        {Array.from({ length: 6 }, (_, i) => i).map((s) => (
          <div key={s} className="flex items-center gap-1 md:gap-2 flex-1">
            <div
              aria-current={s === step ? 'step' : undefined}
              className={cn(
                'w-7 h-7 md:w-8 md:h-8 rounded-full flex items-center justify-center text-xs md:text-sm font-mono font-bold shrink-0 transition-all',
                s < step
                  ? 'bg-brand-primary text-white'
                  : s === step
                    // 当前步骤加光环：在一条水平指示器里仅靠描边区分"当前"太弱
                    ? 'bg-brand-primary/20 text-brand-primary border-2 border-brand-primary ring-4 ring-brand-primary/15'
                    : 'bg-bg-card text-text-muted border border-border'
              )}
            >
              {s < step ? <CheckCircle2 className="w-3.5 h-3.5 md:w-4 md:h-4" strokeWidth={1.25} /> : s}
            </div>
            <span className={cn(
              'text-xs md:text-sm hidden md:inline font-display',
              s === step
                ? 'text-text-primary font-semibold'
                : s < step
                  ? 'text-text-secondary'
                  : 'text-text-muted'
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

            {droppedSkill && (
              <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-warm-orange/40 bg-warm-orange/5 p-3">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.5} />
                <div className="text-xs text-text-secondary leading-relaxed">
                  <p className="text-warm-orange font-medium mb-1">
                    「{droppedSkill}」还不能用来创建评审
                  </p>
                  <p>它目前不会改变评审的跑法，选了也等于没选，所以这里没有替你选上。请另选一个技能。</p>
                </div>
              </div>
            )}

            {skillsLoading && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4" aria-busy="true">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="h-40 rounded-xl border-2 border-border bg-bg-card animate-pulse" />
                ))}
              </div>
            )}

            {/* 加载失败不能表现成「一个技能都没有」——用户会以为技能被停用了 */}
            {!skillsLoading && skillsError && (
              <div className="rounded-xl border-2 border-severity-critical/30 bg-severity-critical/5 p-6 text-center">
                <AlertTriangle className="w-7 h-7 mx-auto mb-2 text-severity-critical" strokeWidth={1.25} />
                <p className="text-sm text-text-primary font-medium mb-1">技能列表没能加载出来</p>
                <p className="text-xs text-text-secondary mb-4">{skillsError}</p>
                <button
                  onClick={loadSkills}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-primary-dim transition-colors"
                >
                  <RefreshCw className="w-4 h-4" strokeWidth={1.5} />
                  重新加载
                </button>
              </div>
            )}

            {!skillsLoading && !skillsError && skills?.length === 0 && (
              <div className="rounded-xl border border-border bg-bg-card p-6 text-center text-sm text-text-secondary">
                当前账号下没有可用于创建评审的技能。
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {(skills ?? []).map((skill) => (
                <button
                  key={skill.type}
                  onClick={() => setSelectedSkillType(skill.type)}
                  className={cn(
                    'flex flex-col p-5 rounded-xl border-2 transition-all cursor-pointer text-left',
                    'bg-bg-card hover:bg-bg-card-hover',
                    selectedSkillType === skill.type
                      ? `${skill.deco?.border ?? 'border-brand-primary/30'} ${skill.deco?.bg ?? 'bg-brand-primary/10'}`
                      : 'border-border hover:border-border-hover'
                  )}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-brand-primary/20 bg-brand-primary/10">
                      <SkillIcon skill={skill} className="h-6 w-6" />
                    </span>
                    <div>
                      {/* 名称与描述都用后端返回的那份：本地再存一份必然和引擎实际读的漂移，
                          表现是同一个技能在技能中心和这一页显示两种说法 */}
                      <h3 className={cn('font-bold font-display', skill.deco?.color ?? 'text-brand-primary')}>{skill.name}</h3>
                      <span className="text-xs text-text-muted font-mono">{skill.type}</span>
                    </div>
                  </div>
                  <p className="text-sm text-text-secondary leading-relaxed mb-3">{skill.description}</p>
                  {/* 这里原本还显示"{skill.persona_count} 个角色"。那个数是本地常量里
                      写死的（6/8/5/10），没有任何事实源，而且 persona_generate 标的 10
                      超过了所有评审模式的人数上限 8——是个可以被当场证伪的数。
                      技能中心那一页已经删掉它，这一页漏了，同一个假数还在站内另一处显示。
                      不拿别的数补位：卡片上少一个数字，好过多一个假的。

                      "N 种任务"同理：以前数的是本地手写的 task_types，后端根本没有这条
                      约束。现在只在后端真的声明了 task_types 时才报数，没声明就不显示。 */}
                  {skill.taskTypes && (
                    <div className="flex items-center gap-3 text-xs text-text-muted">
                      <span>{skill.taskTypes.length} 种任务</span>
                    </div>
                  )}
                  {skill.deco && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {skill.deco.use_cases.slice(0, 3).map((uc) => (
                        <span key={uc} className="px-1.5 py-0.5 rounded text-[10px] bg-bg-secondary text-text-secondary">{uc}</span>
                      ))}
                    </div>
                  )}
                </button>
              ))}
            </div>

            {selectedSkill && (
              <div className={cn('mt-6 rounded-xl border p-4', selectedSkill.deco?.border ?? 'border-brand-primary/30', selectedSkill.deco?.bg ?? 'bg-brand-primary/10')}>
                <div className="flex items-center gap-2 mb-2">
                  <SkillIcon skill={selectedSkill} className="h-5 w-5" />
                  <span className={cn('font-medium text-sm', selectedSkill.deco?.color ?? 'text-brand-primary')}>{selectedSkill.name}</span>
                </div>
                <p className="text-sm text-text-secondary">{selectedSkill.description}</p>
                {selectedSkill.taskTypes && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {selectedSkill.taskTypes.map((tt) => {
                      const taskType = TASK_TYPES.find((t) => t.id === tt)
                      return taskType ? (
                        <span key={tt} className="px-2 py-0.5 rounded text-xs bg-bg-secondary text-text-secondary">
                          {taskType.icon} {taskType.name}
                        </span>
                      ) : null
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {step === 1 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">选择任务类型</h2>
            <p className="text-sm text-text-secondary mb-6">
              {/* 只有后端真的声明了 task_types 时才说「该技能支持的任务类型」，
                  否则这句话是在替后端发明一条它没有的限制 */}
              {selectedSkill
                ? selectedSkill.taskTypes
                  ? `当前技能：${selectedSkill.name} · 以下为该技能声明支持的任务类型`
                  : `当前技能：${selectedSkill.name} · 它没有限定任务类型，下面全部可选`
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

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
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

            <div className="space-y-6">
            <div className="flex items-center gap-2">
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

            <div>
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

              {/* AI 从文件里提取出来、但当前任务类型没有对应字段的内容。
                  以前这些键只存在于 state 里：界面不渲染、确认页不统计，提交时却照发，
                  用户看不见也删不掉自己交上去的东西。 */}
              {extraFieldKeys.length > 0 && (
                <div className="pt-2">
                  <p className="text-xs text-text-muted mb-2">
                    以下内容是从文件里提取出来的，不属于「{TASK_TYPES.find((t) => t.id === selectedTaskType)?.name ?? '当前任务类型'}」的标准字段，
                    但会一并提交给评审员。不需要的话清空即可。
                  </p>
                  {extraFieldKeys.map((key) => (
                    <div key={key} className="mb-3">
                      <label className="block text-sm font-medium text-text-secondary mb-1.5">{key}</label>
                      <textarea
                        value={materialFields[key] ?? ''}
                        onChange={(e) => updateField(key, e.target.value)}
                        rows={3}
                        className="w-full px-4 py-3 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-brand-primary transition-colors resize-y"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">选择角色包</h2>
            <p className="text-sm text-text-secondary mb-6">选择一个角色包快速填充，或手动选择角色</p>

            {/* 本步各块间距统一一档（space-y-6），不再各自带 mb-4/mb-6/mb-8 */}
            <div className="space-y-6">
            <div className="rounded-xl border border-border bg-bg-card p-4">
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

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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

            <h3 className="text-lg font-semibold text-text-primary">
              角色列表
              <span className="text-sm font-normal text-text-muted ml-2">
                已选择 {selectedPersonaIds.size} / 上限 {modeMax} 个
              </span>
            </h3>

            {/* 会被后端静默改写的组合，在这里就说清楚，而不是等报告出来人对不上 */}
            {packConflict && (
              <div className="flex items-start gap-2.5 rounded-xl border border-severity-critical/40 bg-severity-critical/5 p-3">
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
              <div className="flex items-start gap-2.5 rounded-xl border border-warm-orange/40 bg-warm-orange/5 p-3">
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
                  {/* 维度名与个数都取自 EVALUATION_DIMENSIONS（它的 id 逐字对齐后端
                      evaluation_service.RUBRIC_DIMENSIONS，有 parity 测试钉着）。
                      这里以前写死了另一套词表——覆盖度/深度/一致性/证据质量/偏见检测/新颖性/伦理安全，
                      与后端真正评的维度只有「可行动性」一条重合：用户在这里被承诺评 A，
                      报告里拿到的是 B。个数同理，写死的 8 会在后端加减维度时变成假数。 */}
                  <p className="text-xs text-text-secondary leading-relaxed">
                    评审完成后自动运行 {EVALUATION_DIMENSIONS.length} 维度评估，生成评分卡和伦理报告。
                  </p>
                  {enableEvaluation && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {EVALUATION_DIMENSIONS.map((d) => (
                        <span key={d.id} className="px-2 py-0.5 rounded text-xs bg-cyan/10 text-cyan">{d.name}</span>
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

            <div className="space-y-4">
              {selectedSkill && (
                <div className={cn('rounded-xl border p-4 md:p-5', selectedSkill.deco?.border ?? 'border-brand-primary/30', selectedSkill.deco?.bg ?? 'bg-brand-primary/10')}>
                  <h3 className="text-sm font-medium text-text-muted mb-2">评审技能</h3>
                  <div className="flex items-center gap-2">
                    <SkillIcon skill={selectedSkill} className="h-5 w-5" />
                    <span className={cn('font-medium text-sm', selectedSkill.deco?.color ?? 'text-brand-primary')}>{selectedSkill.name}</span>
                  </div>
                </div>
              )}

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
                    {/* 分母要把「额外字段」算进去，否则会出现已填 5 / 共 3 项这种数
                        （提取出来的键不在标准字段里时），或者反过来把用户真交了的东西不计数 */}
                    <span className="ml-2 text-brand-primary">{filledMaterialsCount}</span>
                    <span className="text-text-muted"> / {currentFields.length + extraFieldKeys.length} 项已填写</span>
                  </h3>
                  {materialsExpanded
                    ? <ChevronUp className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                    : <ChevronDown className="w-4 h-4 text-text-muted" strokeWidth={1.25} />
                  }
                </button>
                {materialsExpanded && (
                  <div className="mt-3 space-y-2">
                    {extraFieldKeys.map((key) => (
                      <div key={key} className="flex items-start gap-2 text-sm">
                        <span className="text-text-secondary shrink-0">{key}：</span>
                        <span className="text-text-primary line-clamp-3">{materialFields[key]}</span>
                      </div>
                    ))}
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

              {/* 这里原本是一块「预估成本 $X.XX」。
                  它由一张写死在本文件里的每任务类型单价表算出（0.04~0.10 美元/角色，
                  外加评估 $0.05、红队 $0.08），这些数字追溯不到任何事实源：真实成本由
                  实际消耗的 token 数 × 所用模型的定价决定（引擎侧 runner.persona_agent.estimate_cost
                  读 budget.yaml 的定价表），而 token 数取决于材料长度和模型输出，
                  发起之前谁都不知道。材料贴一万字和贴一句话在这张表里是同一个价。
                  后端也没有任何「预估」端点可以调。
                  所以整块删掉，只说清楚真实成本什么时候能看到——写一个精确到分的假数，
                  比不写更糟：用户会拿它做预算，然后在账单上看到完全不同的数字。 */}
              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <h3 className="text-sm font-medium text-text-muted mb-2">成本</h3>
                <p className="text-sm text-text-secondary leading-relaxed">
                  实际成本取决于材料长度、角色数量和所用模型，发起前无法准确预估。
                  评审跑完后，报告页与评审记录里会显示这次真实消耗的 token 与费用。
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 底部操作区：主按钮（下一步/启动）始终右对齐，错误说明放在主按钮上方
          而不是挤在它旁边，窄屏不再被长错误文案顶歪 */}
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
          <div className="flex flex-col items-end gap-2">
            {launchError && (
              <p className="max-w-md text-right text-sm text-severity-critical">{launchError}</p>
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
