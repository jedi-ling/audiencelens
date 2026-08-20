import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { cn } from '@/lib/utils'
import { TASK_TYPES, PACK_ICONS, TASK_TYPE_CATEGORIES } from '@/lib/mock-data'
import type { Persona, TaskMaterialField, Example, ReviewMode, SkillType } from '@/lib/mock-data'
import { extractMaterials } from '@/lib/api'
import { usePersonaStore, packName } from '@/store/persona-store'
import { useReviewStore } from '@/store/review-store'
import { loadSkillTruth, NON_REVIEW_SKILL_TYPES } from '@/lib/skills'
import type { SkillTruth } from '@/lib/skills'
import TaskTypeCard from '@/components/TaskTypeCard'
import PersonaRadarChart from '@/components/PersonaRadarChart'
import { ArrowLeft, ArrowRight, Upload, CheckCircle2, X, Loader2, ChevronDown, ChevronUp, Star, AlignLeft, FileText, Shield, FlaskConical, AlertTriangle, RefreshCw, Layers } from 'lucide-react'
import { t, Trans } from '@/i18n/runtime'
import {
  getTaskTypes,
  findTaskType,
  getReviewModes,
  findReviewMode,
  getMaterialFields,
  getEvaluationDimensions,
  localizeBackendSkill,
  localizePersona,
} from '@/i18n/catalog'
import { useDocumentTitle } from '@/i18n/head'
import { tApiErrorParts, type ApiErrorText } from '@/i18n/api-error'
import type { PlainMessageKey } from '@/i18n/keys.gen'

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

/**
 * 三种评审模式的显示配置。
 *
 * 存的是 **labelKey 不是文案**：这个对象在模块求值时就固定了，存翻译结果的话
 * 切换语言不会重新求值，模式名会一直停在打开页面时的那种语言。
 * color / bg / border / icon 留在这里不进 key 表——样式与图标不是文案（契约 3.4 例 7）。
 *
 * 档位名读 enum.mode_badge.*（ReviewMode 是后端枚举，按契约 §11 第 3 条走 enum.*），
 * 不在本页另抽一份——各页各抽会让同一个模式在报告页、历史页、这一页出现三种叫法。
 * 「…模式」那半句是本页自己的（page.create.mode_name.value）：中文是后缀，
 * 英文语序不同，拼进枚举值会把英文语序锁死。
 */
const modeConfig: Record<ReviewMode, { labelKey: PlainMessageKey; color: string; bg: string; border: string; icon: string }> = {
  quick: { labelKey: 'enum.mode_badge.quick', color: 'text-cyan', bg: 'bg-cyan/10', border: 'border-cyan/30', icon: '⚡' },
  standard: { labelKey: 'enum.mode_badge.standard', color: 'text-brand-primary', bg: 'bg-brand-primary/10', border: 'border-brand-primary/30', icon: '✅' },
  full: { labelKey: 'enum.mode_badge.full', color: 'text-warm-orange', bg: 'bg-warm-orange/10', border: 'border-warm-orange/30', icon: '🔬' },
}

/** 红队对抗的四个典型场景。同样存 key 不存文案，理由见 modeConfig。 */
const RED_TEAM_CASE_KEYS: PlainMessageKey[] = [
  'page.create.red_team_case_pricing.badge',
  'page.create.red_team_case_community.badge',
  'page.create.red_team_case_localization.badge',
  'page.create.red_team_case_pr.badge',
]

/** "3" 或 "4-6"。两端相同时不写成 "3-3"。 */
function formatCountRange(range: readonly [number, number]): string {
  return range[0] === range[1] ? `${range[0]}` : `${range[0]}-${range[1]}`
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
/**
 * 兜底字段的 key。它会被当成 `materials[].type` 发给后端，和 TASK_MATERIALS[].key
 * 是同一个位置、同一条规矩：**wire 值不是文案，永不翻译**（契约 12.2）。
 */
const GENERIC_MATERIAL_KEY = '材料正文'

/**
 * label / placeholder 必须在渲染时才求值。写成模块级常量会把翻译结果固定在模块
 * 求值那一刻，切换语言时这个兜底字段不会跟着变——而它出现的场合恰恰是
 * "这个任务类型还没配字段"，界面上只有它一个输入框，语言不对格外显眼。
 */
function genericMaterialField(): TaskMaterialField {
  return {
    key: GENERIC_MATERIAL_KEY,
    label: t('page.create.generic_field.label'),
    placeholder: t('page.create.generic_field.placeholder'),
    required: true,
  }
}

export default function CreateReviewPage() {
  const navigate = useNavigate()
  // 标签页标题。它内部 useLocale()，顺带让整页在切语言时重渲染——
  // t() 是普通函数、不带响应性，没有这一步文案会停在打开页面时的语言。
  useDocumentTitle('page.create.meta.title')
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
  // 错误态存 { text, detail } 而不是一句拼好的字符串：非中文界面下后端中文原文
  // 要降级进 title 属性，而不是与英文界面混排、也不是被丢掉（契约 D2）。
  const [launchError, setLaunchError] = useState<ApiErrorText | null>(null)
  const [materialsExpanded, setMaterialsExpanded] = useState(false)
  const [examplesExpanded, setExamplesExpanded] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [extractError, setExtractError] = useState<ApiErrorText | null>(null)
  const [enableEvaluation, setEnableEvaluation] = useState(false)
  const [enableRedTeam, setEnableRedTeam] = useState(false)
  // 两层评审：全包初筛 → 分歧门禁 → 深评。默认关——它比常规评审多一轮
  // （廉价档）调用，该由用户显式选择而不是替他决定花这笔钱。
  const [wideScreen, setWideScreen] = useState(false)
  // 技能清单以 /api/skills 为唯一事实源。以前第 0 步的名称/描述读的是本地 SKILLS，
  // 后端改了文案这一页不会跟，同一个技能在技能中心和创建页会显示两种说法。
  const [skills, setSkills] = useState<SkillTruth[] | null>(null)
  const [skillsError, setSkillsError] = useState<ApiErrorText | null>(null)
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
        setSkillsError(tApiErrorParts(e, 'page.create.skill_list.error'))
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
  // 技能名与描述按 ui_lang 取（后端只回中文，理由见 i18n/catalog.ts §B2）。
  // 三处显示（第 0 步选中卡、第 1 步说明句、第 5 步确认页）共用这一份，
  // 免得同一个技能在同一条流程里出现两种叫法。
  const selectedSkillText = selectedSkill ? localizeBackendSkill(selectedSkill) : null

  /**
   * 材料字段走 getMaterialFields 而不是直读 TASK_MATERIALS：
   * 源常量里的 label / placeholder 是中文字面量，直读的话英文界面上整张表单是中文，
   * 而且是看不出缺译的那种中文。`?? []` 那条数据缺口语义由读取器保留（见其注释），
   * 所以下面 GENERIC_MATERIAL_FIELD 的兜底分支一行没变。
   */
  const definedFields: readonly TaskMaterialField[] = selectedTaskType
    ? getMaterialFields(selectedTaskType)
    : []
  /** 真正渲染与校验用的字段。没有定义时退回一个必填的通用正文框，见 GENERIC_MATERIAL_FIELD。 */
  const currentFields: readonly TaskMaterialField[] =
    selectedTaskType && definedFields.length === 0 ? [genericMaterialField()] : definedFields

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
  // 名称/描述按 ui_lang 取好再过滤：TaskTypeCard 直接渲染传进去的 name / description，
  // 直读 TASK_TYPES 的话英文界面上这一屏卡片全是中文。过滤逻辑一行没改。
  const localizedTaskTypes = getTaskTypes()
  const filteredTaskTypes = skillTaskTypes
    ? localizedTaskTypes.filter((tt) => skillTaskTypes.includes(tt.id))
    : localizedTaskTypes

  const requiredFields = currentFields.filter((f) => f.required)

  // 模式描述同样走 overlay（档位名仍是 enum.mode_badge.*，见 i18n/catalog.ts §B1 末段）。
  const currentModeConfig = findReviewMode(selectedMode)
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
  // 包名不再在本页自己查（原来是 `packs.find(...)?.name ?? id`）：后端回的 name 是中文，
  // 英文界面上就是"混中文且没人发现"（契约 D8），`?? id` 更会让用户以为 "game-core"
  // 是包名。统一走 store 的 packName()——包名的 owner 是它的 PACK_NAME_KEY +
  // catalog.persona_pack（D5 表里包名的 zh / en 事实源都是前端），查不到显式 ⟦missing:…⟧。

  // 在渲染里求值（而不是模块级常量）：切语言时要跟着变。
  const stepLabels: Record<Step, string> = {
    0: t('page.create.stage.skill'),
    1: t('page.create.stage.task_type'),
    2: t('page.create.stage.material'),
    3: t('page.create.stage.persona'),
    4: t('page.create.stage.option'),
    5: t('page.create.stage.confirm'),
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
      setLaunchError({ text: t('page.create.launch_pack_mismatch.error') })
      setStep(3)
      return
    }
    const materials = Object.entries(materialFields)
      .filter(([, value]) => value.trim() !== '')
      .map(([type, description]) => ({ type, description }))
    // 空材料的评审不发出去：引擎只能拿标题当全部输入，跑出来是一份看着正常
    // 却什么都没读过的报告，用户没法从结果里看出自己漏交了东西。
    if (materials.length === 0) {
      setLaunchError({ text: t('page.create.launch_no_material.error') })
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
        wide_screen: wideScreen,
      })
      navigate(`/review/${reviewId}`)
    } catch (e) {
      setLaunchError(tApiErrorParts(e, 'page.create.launch.error'))
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
      // 中文界面 reason.text 就是后端原文；非中文界面是按 code 出的前端译文，
      // 后端中文原文进 reason.detail，由渲染处放进 title 属性，不与英文并排显示。
      const reason = tApiErrorParts(e, 'page.create.extract_reason_unknown.error')
      setExtractError({
        text: t('page.create.extract.error', { reason: reason.text }),
        detail: reason.detail,
      })
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
            <h2 className="text-xl font-semibold text-text-primary mb-2">{t('page.create.skill.title')}</h2>
            <p className="text-sm text-text-secondary mb-6">{t('page.create.skill.desc')}</p>

            {droppedSkill && (
              <div className="mb-4 flex items-start gap-2.5 rounded-xl border border-warm-orange/40 bg-warm-orange/5 p-3">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.5} />
                <div className="text-xs text-text-secondary leading-relaxed">
                  <p className="text-warm-orange font-medium mb-1">
                    {t('page.create.dropped_skill.title', { skill: droppedSkill })}
                  </p>
                  <p>{t('page.create.dropped_skill.desc')}</p>
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
                <p className="text-sm text-text-primary font-medium mb-1">{t('page.create.skill_error.title')}</p>
                {/* detail 是后端原文，语种可能与界面不一致——放 title 属性，不与主文案并排 */}
                <p className="text-xs text-text-secondary mb-4" title={skillsError.detail}>{skillsError.text}</p>
                <button
                  onClick={loadSkills}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-primary text-white text-sm font-medium hover:bg-brand-primary-dim transition-colors"
                >
                  <RefreshCw className="w-4 h-4" strokeWidth={1.5} />
                  {t('page.create.skill_error.cta')}
                </button>
              </div>
            )}

            {!skillsLoading && !skillsError && skills?.length === 0 && (
              <div className="rounded-xl border border-border bg-bg-card p-6 text-center text-sm text-text-secondary">
                {t('page.create.skill_list.empty')}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {(skills ?? []).map((skill) => {
                // 卡片上的名称/描述与下面选中详情走**同一个** localizeBackendSkill：
                // 只给详情接本地化、卡片直接渲染后端原文，表现是同一个技能在同一屏上
                // 卡片是中文、详情是英文。
                const skillText = localizeBackendSkill(skill)
                return (
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
                      <h3 className={cn('font-bold font-display', skill.deco?.color ?? 'text-brand-primary')}>{skillText.name}</h3>
                      <span className="text-xs text-text-muted font-mono">{skill.type}</span>
                    </div>
                  </div>
                  <p className="text-sm text-text-secondary leading-relaxed mb-3">{skillText.description}</p>
                  {/* 这里原本还显示"{skill.persona_count} 个角色"。那个数是本地常量里
                      写死的（6/8/5/10），没有任何事实源，而且 persona_generate 标的 10
                      超过了所有评审模式的人数上限 8——是个可以被当场证伪的数。
                      技能中心那一页已经删掉它，这一页漏了，同一个假数还在站内另一处显示。
                      不拿别的数补位：卡片上少一个数字，好过多一个假的。

                      "N 种任务"同理：以前数的是本地手写的 task_types，后端根本没有这条
                      约束。现在只在后端真的声明了 task_types 时才报数，没声明就不显示。 */}
                  {skill.taskTypes && (
                    <div className="flex items-center gap-3 text-xs text-text-muted">
                      <span>{t('page.create.skill_card.meta', { count: skill.taskTypes.length })}</span>
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
                )
              })}
            </div>

            {selectedSkill && selectedSkillText && (
              <div className={cn('mt-6 rounded-xl border p-4', selectedSkill.deco?.border ?? 'border-brand-primary/30', selectedSkill.deco?.bg ?? 'bg-brand-primary/10')}>
                <div className="flex items-center gap-2 mb-2">
                  <SkillIcon skill={selectedSkill} className="h-5 w-5" />
                  <span className={cn('font-medium text-sm', selectedSkill.deco?.color ?? 'text-brand-primary')}>{selectedSkillText.name}</span>
                </div>
                <p className="text-sm text-text-secondary">{selectedSkillText.description}</p>
                {selectedSkill.taskTypes && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {selectedSkill.taskTypes.map((tt) => {
                      // findTaskType 已按 ui_lang 取好 name（直读 TASK_TYPES 会漏中文出来）。
                      // 后端声明了一个本地没有的 id 就不渲染这一条，与原来的行为一致。
                      const taskType = findTaskType(tt)
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
            <h2 className="text-xl font-semibold text-text-primary mb-2">{t('page.create.task_type.title')}</h2>
            <p className="text-sm text-text-secondary mb-6">
              {/* 只有后端真的声明了 task_types 时才说「该技能支持的任务类型」，
                  否则这句话是在替后端发明一条它没有的限制 */}
              {selectedSkill && selectedSkillText
                ? selectedSkill.taskTypes
                  ? t('page.create.task_type_scoped.desc', { skill: selectedSkillText.name })
                  : t('page.create.task_type_open.desc', { skill: selectedSkillText.name })
                : t('page.create.task_type.desc')}
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
                <span>{t('page.create.category_all.tab')}</span>
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
                    {/* ⚠ TASK_TYPE_CATEGORIES[].name 是中文字面量，英文界面上这一排分类
                        按钮今天仍是中文。它与 TaskTypesPage 的分类名是**同一批目录数据**、
                        中文逐字相同，而现有 owner 是 page.task_types.category_*.label。
                        按契约 §11 第 4 条，"两处逐字相同"要各抽各的、并把合并与否交给
                        batch-0 决定——所以这里不复用那份 key，也不就地再抽一份。
                        建议整批迁到 catalog.task_type_category.*（与 PACK_CATEGORIES 同级）。
                        已写进交付报告。 */}
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
              const tt = findTaskType(selectedTaskType)
              if (!tt) return null
              return (
                <div className="mt-6 rounded-xl border border-border bg-bg-card p-4">
                  <h3 className="text-sm font-medium text-text-muted mb-3">{t('page.create.mode.title')}</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {/* getReviewModes() 而不是 REVIEW_MODES：description 要按 ui_lang 取，
                        直读源常量的话英文界面上三张模式卡的说明全是中文。
                        档位名仍走 mc.labelKey（enum.mode_badge.*），owner 没变。 */}
                    {getReviewModes().map((rm) => {
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
                              {t(mc.labelKey)}
                            </span>
                            <span className="ml-auto text-xs text-text-muted font-mono">
                              {t('page.create.mode_card.unit', { range: formatCountRange(rm.persona_count_range) })}
                            </span>
                          </div>
                          <p className="text-xs text-text-secondary w-full">{rm.description}</p>
                          <div className="flex items-center gap-2 w-full text-xs text-text-muted">
                            {rm.cross_examination && <span className="px-1.5 py-0.5 rounded bg-cyan/10 text-cyan">{t('page.create.feature_cross_exam.badge')}</span>}
                            {rm.calibration && <span className="px-1.5 py-0.5 rounded bg-warm-orange/10 text-warm-orange">{t('page.create.feature_calibration.badge')}</span>}
                            {!rm.cross_examination && !rm.calibration && <span className="text-text-muted/50">{t('page.create.feature_none.badge')}</span>}
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
            <h2 className="text-xl font-semibold text-text-primary mb-2">{t('page.create.material.title')}</h2>
            <p className="text-sm text-text-secondary mb-6">{t('page.create.material.desc')}</p>

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
                {t('page.create.input_mode_text.tab')}
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
                {t('page.create.input_mode_file.tab')}
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
                    <p className="text-sm text-brand-primary font-medium">{t('page.create.extract.pending')}</p>
                    <p className="text-xs text-text-muted mt-1">{t('page.create.extract.hint')}</p>
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 mx-auto mb-3 text-text-muted" strokeWidth={1.25} />
                    <p className="text-sm text-text-secondary">
                      <Trans
                        k="page.create.dropzone.cta"
                        slots={{ click: (s) => <span className="text-brand-primary">{s}</span> }}
                      />
                    </p>
                    <p className="text-xs text-text-muted mt-1">
                      {t('page.create.dropzone.hint')}
                    </p>
                  </>
                )}
                {extractError && (
                  <p className="text-xs text-severity-critical mt-2" title={extractError.detail}>{extractError.text}</p>
                )}
                {filledMaterialsCount > 0 && !extracting && (
                  <p className="text-xs text-brand-primary mt-2">
                    {t('page.create.extract.success', { count: filledMaterialsCount })}
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
                    {t('page.create.examples.cta')}
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
              <label className="block text-sm font-medium text-text-secondary mb-2">{t('page.create.target.label')}</label>
              <input
                type="text"
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder={t('page.create.target.placeholder')}
                className="w-full px-4 py-3 rounded-lg bg-bg-card border border-border text-text-primary placeholder-text-muted focus:outline-none focus:border-brand-primary transition-colors"
              />
            </div>

            <div className="space-y-4 mb-6">
              <div className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-2 mb-3">
                <h3 className="text-sm font-medium text-text-secondary">{t('page.create.fields.title')}</h3>
                {filledMaterialsCount > 0 && (
                  <span className="text-xs text-brand-primary">{t('page.create.fields.hint', { count: filledMaterialsCount })}</span>
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
                    {t('page.create.extra_fields.desc', {
                      taskType:
                        findTaskType(selectedTaskType)?.name
                        ?? t('page.create.extra_fields_unknown.label'),
                    })}
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
            <h2 className="text-xl font-semibold text-text-primary mb-2">{t('page.create.persona.title')}</h2>
            <p className="text-sm text-text-secondary mb-6">{t('page.create.persona.desc')}</p>

            {/* 本步各块间距统一一档（space-y-6），不再各自带 mb-4/mb-6/mb-8 */}
            <div className="space-y-6">
            <div className="rounded-xl border border-border bg-bg-card p-4">
              <h3 className="text-sm font-medium text-text-muted mb-3">{t('page.create.mode_summary.title')}</h3>
              <div className="flex items-center gap-2">
                <span className="text-lg">{modeConfig[selectedMode].icon}</span>
                <span className={cn('font-medium text-sm', modeConfig[selectedMode].color)}>
                  {t('page.create.mode_name.value', { mode: t(modeConfig[selectedMode].labelKey) })}
                </span>
                {/* 取不到模式配置时整句不渲染。原先会渲染成"·  个角色"——
                    一个没有数字的人数说明，比不说更让人以为是界面坏了 */}
                {currentModeConfig && (
                  <span className="text-xs text-text-muted">
                    {t('page.create.mode_summary.unit', { range: formatCountRange(currentModeConfig.persona_count_range) })}
                  </span>
                )}
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
                    {packName(pack.panel_id)}
                  </span>
                  <span className="text-xs text-text-muted">{t('page.create.pack_card.unit', { count: pack.persona_count })}</span>
                </button>
              ))}
            </div>

            {selectedPack && (() => {
              const pack = packs.find((p) => p.panel_id === selectedPack)
              if (!pack) return null
              return (
                <div className="mb-8 px-4 py-3 rounded-lg bg-brand-primary/5 border border-brand-primary/20">
                  <p className="text-sm text-text-secondary">
                    {/* 冒号也进消息串：中文是全角「：」，英文是半角「: 」，不是同一个字符 */}
                    {/* ⚠ desc 仍是后端回的中文：包**名**的 owner 在前端（走 packName），
                        包**描述**在前端没有任何 owner——mock-data 的 PERSONA_PACKS 早已删除，
                        所以 i18n:sync-catalog 生成不出它的 zh 侧，只有 en 侧一半的话
                        i18n:check 的 zh/en key 集相等断言会红。后端 catalog.en-US.json 的
                        persona_packs[].description 已经有英文，缺的是下发通道
                        （packs 端点还不发 description_en）。已写进交付报告。 */}
                    <Trans
                      k="page.create.pack_intro.desc"
                      vars={{ name: packName(pack.panel_id), desc: pack.description }}
                      slots={{ name: (s) => <span className="text-brand-primary font-medium">{s}</span> }}
                    />
                  </p>
                </div>
              )
            })()}

            <h3 className="text-lg font-semibold text-text-primary">
              {t('page.create.persona_list.title')}
              <span className="text-sm font-normal text-text-muted ml-2">
                {t('page.create.persona_list.meta', { count: selectedPersonaIds.size, max: modeMax })}
              </span>
            </h3>

            {/* 会被后端静默改写的组合，在这里就说清楚，而不是等报告出来人对不上 */}
            {packConflict && (
              <div className="flex items-start gap-2.5 rounded-xl border border-severity-critical/40 bg-severity-critical/5 p-3">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-severity-critical" strokeWidth={1.5} />
                <div className="text-xs text-text-secondary leading-relaxed">
                  <p className="text-severity-critical font-medium mb-1">
                    {t('page.create.pack_conflict.title', {
                      count: selectedPackIds.length,
                      // 分隔符也进 key 表：中文顿号在英文里读不通
                      packs: selectedPackIds.map(packName).join(t('page.create.pack_conflict.value')),
                    })}
                  </p>
                  <p>{t('page.create.pack_conflict.desc')}</p>
                </div>
              </div>
            )}
            {!packConflict && overModeMax && (
              <div className="flex items-start gap-2.5 rounded-xl border border-warm-orange/40 bg-warm-orange/5 p-3">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-warm-orange" strokeWidth={1.5} />
                <div className="text-xs text-text-secondary leading-relaxed">
                  <p className="text-warm-orange font-medium mb-1">
                    {t('page.create.over_max.title', { mode: t(modeConfig[selectedMode].labelKey), max: modeMax })}
                  </p>
                  <p>
                    {t('page.create.over_max.desc', { max: modeMax, count: selectedPersonaIds.size - modeMax })}
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
            <h2 className="text-xl font-semibold text-text-primary mb-2">{t('page.create.option.title')}</h2>
            <p className="text-sm text-text-secondary mb-6">{t('page.create.option.desc')}</p>

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
                      {t('page.create.evaluation.label')}
                    </span>
                  </div>
                  {/* 维度名与个数都取自 EVALUATION_DIMENSIONS（它的 id 逐字对齐后端
                      evaluation_service.RUBRIC_DIMENSIONS，有 parity 测试钉着）。
                      这里以前写死了另一套词表——覆盖度/深度/一致性/证据质量/偏见检测/新颖性/伦理安全，
                      与后端真正评的维度只有「可行动性」一条重合：用户在这里被承诺评 A，
                      报告里拿到的是 B。个数同理，写死的 8 会在后端加减维度时变成假数。
                      读的是 i18n/catalog.ts 的 getEvaluationDimensions()：它按 ui_lang 取
                      name（id 与个数都还是源常量那份），直读源常量的话英文界面上这一排
                      维度标签全是中文，且看不出是缺译。 */}
                  <p className="text-xs text-text-secondary leading-relaxed">
                    {t('page.create.evaluation.desc', { count: getEvaluationDimensions().length })}
                  </p>
                  {enableEvaluation && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {getEvaluationDimensions().map((d) => (
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
                      {t('page.create.red_team.label')}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    {t('page.create.red_team.desc')}
                  </p>
                  {enableRedTeam && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {RED_TEAM_CASE_KEYS.map((k) => (
                        <span key={k} className="px-2 py-0.5 rounded text-xs bg-red-400/10 text-red-400">{t(k)}</span>
                      ))}
                    </div>
                  )}
                </div>
              </button>

              {/* 两层评审。这个开关此前**只存在于 API**：引擎、门禁、测试、四形态
                  渲染全都做完了，而界面上没有任何地方能打开它——建了没人够得着。
                  显式点名人格时引擎会自动让位（初筛整层跳过），所以这里不做互斥禁用，
                  由引擎按同一条纪律决定，报告里如实写明 reason。 */}
              <button
                onClick={() => setWideScreen(!wideScreen)}
                className={cn(
                  'w-full flex items-start gap-4 p-5 rounded-xl border-2 transition-all cursor-pointer text-left',
                  'bg-bg-card hover:bg-bg-card-hover',
                  wideScreen ? 'border-warm-orange/50 bg-warm-orange/5' : 'border-border'
                )}
              >
                <div className={cn(
                  'w-5 h-5 rounded border-2 shrink-0 mt-0.5 flex items-center justify-center transition-all',
                  wideScreen ? 'bg-warm-orange border-warm-orange' : 'border-border'
                )}>
                  {wideScreen && <CheckCircle2 className="w-3 h-3 text-white" strokeWidth={1.25} />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <Layers className="w-4 h-4 text-warm-orange" strokeWidth={1.25} />
                    <span className={cn('font-medium text-sm', wideScreen ? 'text-warm-orange' : 'text-text-primary')}>
                      {t('page.create.wide_screen.label')}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary leading-relaxed">
                    {t('page.create.wide_screen.desc')}
                  </p>
                  {wideScreen && (
                    <p className="mt-3 text-xs text-text-muted leading-relaxed">
                      {t('page.create.wide_screen.hint')}
                    </p>
                  )}
                </div>
              </button>
            </div>
          </div>
        )}

        {step === 5 && (
          <div>
            <h2 className="text-xl font-semibold text-text-primary mb-2">{t('page.create.confirm.title')}</h2>
            <p className="text-sm text-text-secondary mb-6">{t('page.create.confirm.desc')}</p>

            <div className="space-y-4">
              {selectedSkill && selectedSkillText && (
                <div className={cn('rounded-xl border p-4 md:p-5', selectedSkill.deco?.border ?? 'border-brand-primary/30', selectedSkill.deco?.bg ?? 'bg-brand-primary/10')}>
                  <h3 className="text-sm font-medium text-text-muted mb-2">{t('page.create.confirm_skill.title')}</h3>
                  <div className="flex items-center gap-2">
                    <SkillIcon skill={selectedSkill} className="h-5 w-5" />
                    <span className={cn('font-medium text-sm', selectedSkill.deco?.color ?? 'text-brand-primary')}>{selectedSkillText.name}</span>
                  </div>
                </div>
              )}

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <h3 className="text-sm font-medium text-text-muted mb-2">{t('page.create.confirm_task_type.title')}</h3>
                {(() => {
                  const tt = findTaskType(selectedTaskType)
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
                <h3 className="text-sm font-medium text-text-muted mb-2">{t('page.create.confirm_mode.title')}</h3>
                <div className="flex items-center gap-2">
                  <span className="text-lg">{modeConfig[selectedMode].icon}</span>
                  <span className={cn('font-medium text-sm', modeConfig[selectedMode].color)}>
                    {t('page.create.mode_name.value', { mode: t(modeConfig[selectedMode].labelKey) })}
                  </span>
                  <span className="text-xs text-text-muted">
                    · {currentModeConfig?.description}
                  </span>
                </div>
              </div>

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <h3 className="text-sm font-medium text-text-muted mb-2">{t('page.create.confirm_target.title')}</h3>
                <p className="text-text-primary">{target || t('page.create.confirm_target.empty')}</p>
              </div>

              <div className="rounded-xl border border-border bg-bg-card p-4 md:p-5">
                <button
                  onClick={() => setMaterialsExpanded(!materialsExpanded)}
                  className="w-full flex items-center justify-between"
                >
                  <h3 className="text-sm font-medium text-text-muted">
                    {t('page.create.confirm_material.title')}
                    {/* 分母要把「额外字段」算进去，否则会出现已填 5 / 共 3 项这种数
                        （提取出来的键不在标准字段里时），或者反过来把用户真交了的东西不计数 */}
                    <span className="ml-2">
                      <Trans
                        k="page.create.confirm_material.meta"
                        vars={{ count: filledMaterialsCount, total: currentFields.length + extraFieldKeys.length }}
                        slots={{ filled: (s) => <span className="text-brand-primary">{s}</span> }}
                      />
                    </span>
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
                        {/* key 是中文 wire key，原样显示；只有它后面那个冒号是文案 */}
                        <span className="text-text-secondary shrink-0">{t('page.create.confirm_field.label', { name: key })}</span>
                        <span className="text-text-primary line-clamp-3">{materialFields[key]}</span>
                      </div>
                    ))}
                    {currentFields.map((field) => {
                      const value = materialFields[field.key]
                      if (!value || value.trim() === '') {
                        return (
                          <div key={field.key} className="flex items-start gap-2 text-sm">
                            <span className="text-text-muted shrink-0">{t('page.create.confirm_field.label', { name: field.label })}</span>
                            <span className="text-text-muted/50 italic">{t('page.create.confirm_field.empty')}</span>
                          </div>
                        )
                      }
                      return (
                        <div key={field.key} className="flex items-start gap-2 text-sm">
                          <span className="text-text-secondary shrink-0">{t('page.create.confirm_field.label', { name: field.label })}</span>
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
                  {t('page.create.confirm_persona.title', { count: selectedPersonas.length })}
                  {effectivePack && (
                    <span className="ml-2 font-normal text-text-muted/80">
                      {t('page.create.confirm_persona.meta', { pack: packName(effectivePack) })}
                    </span>
                  )}
                </h3>
                <div className="flex flex-wrap gap-2">
                  {selectedPersonas.map((p) => (
                    <span
                      key={p.id}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-brand-primary/10 text-brand-primary text-xs"
                    >
                      {/* 10.3 推翻早期裁决：展示名走 localizePersona，p.name 本身不动
                          ——它仍是提交给后端 selected_personas 的那个 id 对应的匹配字段。 */}
                      {localizePersona(p).name}
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
                  <h3 className="text-sm font-medium text-text-muted mb-2">{t('page.create.confirm_extra.title')}</h3>
                  <div className="flex flex-wrap gap-2">
                    {enableEvaluation && (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-cyan/10 text-cyan text-xs">
                        <FlaskConical className="w-3 h-3" strokeWidth={1.25} />
                        {t('page.create.confirm_extra_evaluation.badge')}
                      </span>
                    )}
                    {enableRedTeam && (
                      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-red-400/10 text-red-400 text-xs">
                        <Shield className="w-3 h-3" strokeWidth={1.25} />
                        {t('page.create.confirm_extra_red_team.badge')}
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
                <h3 className="text-sm font-medium text-text-muted mb-2">{t('page.create.cost.title')}</h3>
                <p className="text-sm text-text-secondary leading-relaxed">
                  {t('page.create.cost.desc')}
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
          {/* 通用动作词走 common.action.*（契约 §11 第 2 条），本页不重抽一份 */}
          {t('common.action.prev')}
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
            {t('common.action.next')}
            <ArrowRight className="w-4 h-4" strokeWidth={1.25} />
          </button>
        ) : (
          <div className="flex flex-col items-end gap-2">
            {launchError && (
              <p className="max-w-md text-right text-sm text-severity-critical" title={launchError.detail}>{launchError.text}</p>
            )}
            <button
              onClick={handleLaunch}
              disabled={launching}
              className={cn(
                'flex items-center gap-2 px-6 md:px-8 py-2.5 rounded-lg bg-brand-primary text-white font-bold hover:bg-brand-primary-dim glow-green transition-all text-sm',
                launching && 'opacity-70 cursor-not-allowed'
              )}
            >
              {launching ? <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.25} /> : t('page.create.launch.cta')}
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
          {/* 10.3 推翻早期裁决：展示名走 localizePersona；persona.name 本身仍是
              togglePersona(persona.id) 提交给后端的那个匹配字段，没有被这里换掉。 */}
          <span className="text-sm font-medium text-text-primary">{localizePersona(persona).name}</span>
          <span className="text-xs text-text-muted">{localizePersona(persona).archetype}</span>
          {packLabel && (
            <span className="shrink-0 rounded bg-bg-secondary px-1.5 py-0.5 text-[10px] text-text-muted">
              {packLabel}
            </span>
          )}
        </div>
        <p className="text-xs text-text-secondary mt-0.5 line-clamp-1">{localizePersona(persona).identity_summary}</p>
      </div>
      <div className="shrink-0 hidden sm:block">
        <PersonaRadarChart data={persona.behavior_profile} size={60} mobileSize={48} />
      </div>
    </div>
  )
}
