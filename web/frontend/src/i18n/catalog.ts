/**
 * 目录 overlay 的读取器（契约 4.1 给这个文件留的位置就是"目录 overlay 读取器"）。
 *
 * 两类目录住在这里，读法不同，别混着用：
 *
 * A. **前端就是事实源**的（契约 D5 表的第 2、3 行）——TASK_MATERIALS 的 label /
 *    placeholder（后端只认材料的中文 key，没有 label 这个概念）、EVALUATION_DIMENSIONS
 *    的 name / description（后端只回 id 与分数）。zh / en 都查 t()，一条路径。
 *
 * B. **后端是事实源、前端只有离线兜底**的（D5 表第 1 行）——任务类型 / 评审模式 / 技能。
 *    英文事实源是后端 `app/i18n/catalog.en-US.json`，前端那份
 *    `locales/{zh,en}/catalog.{task_type,skill,mode}.ts` 由 `npm run i18n:sync-catalog`
 *    生成、不许手写，`npm run i18n:check` 逐字节断言它与后端一致（契约 D5）。
 *    这一类分两种取法，见下面 §B1 / §B2 各自的注释：
 *      · 页面读的是**前端源常量**（TutorialPage / CreateReviewPage 的任务类型与模式）
 *        → zh / en 都查 overlay，同 A。
 *      · 页面读的是**后端返回的行**（TaskTypesPage 的清单、SkillSelectPage 的技能）
 *        → zh 用后端原文，en 查 overlay。理由写在 §B2。
 *
 * 人格包名不在这里：D5 表里它的 zh / en 事实源**都是前端**，是唯一事实源不是兜底，
 * owner 是 store/persona-store.ts 的 PACK_NAME_KEY + locales/{zh,en}/catalog.persona_pack.ts。
 * 本文件只补一个包**分类**名的读取器（同一份 catalog.persona_pack 资源，见 §C）。
 *
 * 为什么页面要改走这里，而不是继续直接读 mock-data 的源常量：
 * 源常量里的 label / placeholder 是中文字面量，页面直接读它 = 英文界面上一片中文，
 * 而且是**看不出是缺译**的那种中文（契约纪律 2 点名的形态）。走 t() 之后，
 * 少一条就是 DEV 抛错 / PROD ⟦missing:…⟧。
 *
 * zh 与 en 走**同一条**代码路径（都查 t()），不给中文开一条"直接读源常量"的近路。
 * 两条路径必然长出只在一种语言下发生的 bug：中文界面好好的、英文界面是空的，
 * 而写代码的人用的正是中文界面。代价是 zh overlay 是源常量的副本、会漂移，
 * 所以下面每个函数都带一条 DEV 期的逐字比对断言。
 */

import {
  TASK_MATERIALS,
  EVALUATION_DIMENSIONS,
  TASK_TYPES,
  REVIEW_MODES,
  SKILLS,
  PACK_CATEGORIES,
  type TaskMaterialField,
  type TaskType,
  type ReviewModeConfig,
} from '@/lib/mock-data'
import { t, missingMarker } from './runtime'
import { getLocale } from './locale'

/**
 * 动态拼出来的 key 参与不了 MessageKey 那个字面量联合：材料字段有 76 条 × 2 个角色，
 * 维度有 8 条 × 2 个角色，全部由数据驱动拼出来，写不成字面量。
 *
 * 放宽类型的代价由 t() 自己兜住——查不到就是 DEV 抛 MissingMessageError /
 * PROD 渲染 ⟦missing:…⟧ + console.error，不会静默回落。
 * 同一处理法在 store/persona-store.ts 与 components/PersonaRadarChart.tsx 已有先例，
 * 区别只是那两处的 key 数量少到能写成静态映射表。
 */
const tDyn = t as unknown as (key: string) => string

/** 中文界面下，overlay 与源常量必须逐字相同。不同就是有人只改了一边。 */
function assertZhMatchesSource(key: string, fromOverlay: string, fromSource: string): void {
  if (!import.meta.env.DEV) return
  if (getLocale() !== 'zh') return
  if (fromOverlay === fromSource) return
  throw new Error(
    `i18n 目录 overlay 与源常量漂移：${key}\n` +
      `  locales/zh 里是：${fromOverlay}\n` +
      `  mock-data.ts 里是：${fromSource}\n` +
      `源常量是中文侧的事实源（契约 D6，源行一个字不改），改文案要改的是 mock-data.ts，` +
      `然后把 locales/zh 的这条同步成逐字副本、并重新检查 locales/en 的译文是否还对得上。`,
  )
}

/** 材料字段，label / placeholder 已按当前 ui_lang 取好。形状与 TaskMaterialField 相同。 */
export function getMaterialFields(taskTypeId: string): readonly TaskMaterialField[] {
  // `?? []` 在这里不是"缺译兜底"，是**数据缺口**：这个任务类型在 TASK_MATERIALS 里
  // 根本没有条目。调用方（CreateReviewPage）对空数组有自己的处理（GENERIC_MATERIAL_FIELD），
  // 那是产品行为，不该由 i18n 层替它决定。契约 5.5 给的签名也是这一条。
  const source = TASK_MATERIALS[taskTypeId] ?? []
  return source.map((f) => {
    // key 段里的中文是 wire contract 原文，永不翻译；它同时是这条 overlay 的定位符。
    // 改了 wire key 而没同步 overlay，表现就是这里查不到 → 立刻可见，
    // 而不是"编译通过、界面正常、引擎提取不到材料"。
    const base = `catalog.material.${taskTypeId}__${f.key}`
    const label = tDyn(`${base}.label`)
    const placeholder = tDyn(`${base}.placeholder`)
    assertZhMatchesSource(`${base}.label`, label, f.label)
    assertZhMatchesSource(`${base}.placeholder`, placeholder, f.placeholder)
    return { key: f.key, label, placeholder, required: f.required }
  })
}

export interface LocalizedEvaluationDimension {
  id: string
  name: string
  description: string
}

/** 自评维度，name / description 已按当前 ui_lang 取好。形状与 EVALUATION_DIMENSIONS 相同。 */
export function getEvaluationDimensions(): readonly LocalizedEvaluationDimension[] {
  return EVALUATION_DIMENSIONS.map((d) => {
    const base = `catalog.eval_dimension.${d.id}`
    const name = tDyn(`${base}.label`)
    const description = tDyn(`${base}.desc`)
    assertZhMatchesSource(`${base}.label`, name, d.name)
    assertZhMatchesSource(`${base}.desc`, description, d.description)
    return { id: d.id, name, description }
  })
}

/**
 * 单条维度。ReportPage / EvaluationPage 现在写的是
 * `EVALUATION_DIMENSIONS.find((d) => d.id === r.dimension)`，换成这个。
 *
 * 找不到时返回 undefined 而不是造一条：后端回了一个前端不认识的维度 id，
 * 那是**目录漂移**不是缺译，调用方现有的 undefined 分支已经在处理它
 * （mock-data.ts:985 那段注释记的就是这次事故），i18n 层不该把它伪装成一条正常维度。
 */
export function findEvaluationDimension(id: string): LocalizedEvaluationDimension | undefined {
  return getEvaluationDimensions().find((d) => d.id === id)
}

/* ================================================================== *
 * §B1 后端目录，页面读的是前端源常量的那一批
 *
 * TutorialPage 的任务类型表、CreateReviewPage 的任务类型卡片与模式卡片，读的都是
 * mock-data 的 TASK_TYPES / REVIEW_MODES（这三处离线也要能用，且 D6 规定源行不动）。
 * 所以取法与 §A 完全一样：zh / en 同一条路径，都查 overlay，缺一条就是显式缺译。
 *
 * 注意 overlay 的 zh 侧是**生成物**（i18n:sync-catalog 从这两个源常量照抄），
 * 理论上不可能与源常量不符。下面仍然带 assertZhMatchesSource：它抓的是
 * "有人手改了生成物还没跑 i18n:check"，成本一次字符串比较。
 * ================================================================== */

/**
 * 任务类型全表，name / description 已按当前 ui_lang 取好。
 * 其余字段（id / icon / category / IconComponent / stance_enum / score_dimensions）
 * 原样透传：它们不是文案——stance_enum 更是 wire contract，永不翻译（契约 12.2）。
 */
export function getTaskTypes(): readonly TaskType[] {
  return TASK_TYPES.map((tt) => {
    const base = `catalog.task_type.${tt.id}`
    const name = tDyn(`${base}.label`)
    const description = tDyn(`${base}.desc`)
    assertZhMatchesSource(`${base}.label`, name, tt.name)
    assertZhMatchesSource(`${base}.desc`, description, tt.description)
    return { ...tt, name, description }
  })
}

/**
 * 单条任务类型。找不到返回 undefined 而不是造一条：调用方给的 id 不在本地目录里，
 * 那是**目录漂移**（或用户带了一个过期的 ?task= 链接），不是缺译，
 * 各调用点现有的 undefined 分支已经在处理它。
 */
export function findTaskType(id: string | null): TaskType | undefined {
  if (id === null) return undefined
  return getTaskTypes().find((tt) => tt.id === id)
}

/** 评审模式全表，description 已按当前 ui_lang 取好。档位名不在这里，见 §B1 下方说明。 */
export function getReviewModes(): readonly ReviewModeConfig[] {
  return REVIEW_MODES.map((rm) => {
    const key = `catalog.mode.${rm.mode}.desc`
    const description = tDyn(key)
    assertZhMatchesSource(key, description, rm.description)
    return { ...rm, description }
  })
}

/**
 * 单条评审模式。
 *
 * ⚠ 档位名（快速 / 标准 / 完整）**不在这里**：后端 REVIEW_MODES 没有 name 字段，
 * 它的 owner 是 enum.mode_badge.*（ReviewMode 是后端枚举，按契约 §11 第 3 条走 enum.*）。
 * 各页现在都写 `t(modeConfig[mode].labelKey)`，别改成从这里取——那会让同一个模式
 * 在报告页、历史页、创建页出现两种叫法。
 */
export function findReviewMode(mode: string): ReviewModeConfig | undefined {
  return getReviewModes().find((rm) => rm.mode === mode)
}

/* ================================================================== *
 * §B2 后端目录，页面读的是后端返回的行的那一批
 *
 * TaskTypesPage 的清单（GET /api/task-types）与技能页/创建评审页的技能
 * （GET /api/skills，见 lib/skills.ts 的 SkillTruth）都以后端返回值为
 * "有哪些条目"的唯一事实源——后端新增一个前端没登记的条目，它必须照常显示，
 * 拿本地表当白名单会把后端已经支持的能力静默藏起来（TaskTypesPage 文件头记过这条）。
 *
 * 于是这一类**不能**走 §B1 那条"一律查 overlay"的路：
 *   · zh 用后端原文。后端就是中文事实源，且这样后端新增的条目在中文界面照常可见。
 *   · en 查 overlay。今天后端端点还不发 name_en（catalog_en.py 已就位但尚未被任何
 *     服务引用，数据是惰性的），拉到的 name 是中文；直接渲染它就是"英文界面上一片
 *     看不出是缺译的中文"，正是契约纪律 2 / D8 点名禁止的形态。
 *   · overlay 里也没有 = 后端有、前端不知道的条目，显式 ⟦missing:…⟧ + console.error，
 *     不回落成中文。这条缺口必须有人看得见。
 *
 * 后端把 name_en / description_en 发出来之后，这两个函数改成"优先用行里的 *_en，
 * 没有再查 overlay"，调用点一行不用动——这也是它们收整行而不是收字符串的原因。
 */

/** 是否是前端本地登记过的条目。是 → overlay 里必然有（i18n:check 断言过），可以放心 t()。 */
const KNOWN_TASK_TYPE_IDS = new Set(TASK_TYPES.map((tt) => tt.id))
const KNOWN_SKILL_TYPES = new Set(SKILLS.map((s) => s.type as string))

function fromBackendRow(
  known: Set<string>,
  id: string,
  overlayKey: string,
  zhFromBackend: string,
  what: string,
): string {
  if (getLocale() === 'zh') return zhFromBackend
  if (known.has(id)) return tDyn(overlayKey)
  console.error(`[i18n/catalog] 后端有、前端目录里没有的${what}，overlay 需要补一条：`, id)
  return missingMarker(overlayKey, getLocale())
}

export interface LocalizedCatalogRow {
  name: string
  description: string
}

/** 后端 /api/task-types 的一行。形参收整行，理由见 §B2 末段。 */
export function localizeBackendTaskType(row: {
  task_type: string
  name_zh: string
  description: string
}): LocalizedCatalogRow {
  const id = row.task_type
  return {
    // name_zh 为空时退回 id：这不是缺译，是后端这一行没有名字，
    // 与 TaskTypesPage 原来的 `tt.name_zh || tt.task_type` 是同一个取舍。
    name: fromBackendRow(
      KNOWN_TASK_TYPE_IDS, id, `catalog.task_type.${id}.label`, row.name_zh || id, '任务类型',
    ),
    description: fromBackendRow(
      KNOWN_TASK_TYPE_IDS, id, `catalog.task_type.${id}.desc`, row.description, '任务类型',
    ),
  }
}

/** 后端 /api/skills 的一行（lib/skills.ts 的 SkillTruth 形状）。 */
export function localizeBackendSkill(row: {
  type: string
  name: string
  description: string
}): LocalizedCatalogRow {
  const id = row.type
  return {
    name: fromBackendRow(KNOWN_SKILL_TYPES, id, `catalog.skill.${id}.label`, row.name, '技能'),
    description: fromBackendRow(KNOWN_SKILL_TYPES, id, `catalog.skill.${id}.desc`, row.description, '技能'),
  }
}

/* ================================================================== *
 * §C 人格包分类名
 *
 * 包名的 owner 是 store/persona-store.ts（D5 表里它的 zh / en 事实源都是前端），
 * 分类名与它同属一份资源文件 locales/{zh,en}/catalog.persona_pack.ts 的 category_ 前缀段
 * ——那四条译文一直躺在资源里没有消费方，PersonasPage 直接渲染
 * PACK_CATEGORIES[].name 的中文字面量（zh/catalog.persona_pack.ts 的文件头记过这件事）。
 * 这个函数就是那四条的消费方。
 * ================================================================== */

/**
 * 包分类名。PACK_CATEGORIES 的 id 带连字符（player-type），key 段一律 snake_case（契约 3.1），
 * 所以这里换一次下划线。查不到 → 显式标记，不回落成中文 name。
 */
export function getPackCategoryName(id: string): string {
  const source = PACK_CATEGORIES.find((c) => c.id === id)
  const key = `catalog.persona_pack.category_${id.replace(/-/g, '_')}`
  if (!source) {
    console.error('[i18n/catalog] 未知人格包分类，PACK_CATEGORIES 与 catalog.persona_pack 需要补一条：', id)
    return missingMarker(key, getLocale())
  }
  const name = tDyn(key)
  assertZhMatchesSource(key, name, source.name)
  return name
}

/* ================================================================== *
 * §D 人格的表述层文案（archetype / identity_summary）
 *
 * 与 §B1 / §B2 都不同，所以单开一节：
 *   · §B1 是"前端有源常量"，zh/en 都查 overlay；
 *   · §B2 是"后端只发中文"，en 才查 overlay；
 *   · 人格是**后端把中英并排发下来**（契约 D4，PersonaSummary 的
 *     archetype_en / identity_summary_en，事实源 src/personas/en-US/<pack>.yaml）。
 *     英文既不在前端资源里、也不需要 key 表——它是数据不是 UI 文案，
 *     72 条人格 × 2 个字段塞进 key 表只会让 i18n:check 去校验一批
 *     没有任何页面写死过的字符串。
 *
 * 身份字段（name / gender / age_range / region / language / mbti …）**不经过这里**：
 * 10.3 冻结了它们，张伟在英文界面下仍叫张伟。这个函数只收表述层那两条。
 *
 * 缺 overlay 时**不回落中文**：后端注释写明 null 只有一种含义——这条人格没有
 * overlay（只可能是 .claude/agents / .trae 那两份开发工具链镜像）。
 * 回落成中文的表现是"英文界面里混中文且没人发现"，正是 D8 点名禁止的形态。
 * ================================================================== */

export interface LocalizedPersonaText {
  archetype: string
  identity_summary: string
}

/**
 * 人格的 archetype / identity_summary，按当前 ui_lang 取好。
 *
 * 形参收整条人格而不是两个字符串：调用点（PersonaCard / PersonasPage /
 * CreateReviewPage / ReviewProgressPage / AskPage）都已经拿着整条，
 * 收整行也让"以后再加一条双发字段"不用改调用点签名——同 §B2 末段的理由。
 */
export function localizePersona(p: {
  id: string
  archetype: string
  identity_summary: string
  archetype_en?: string | null
  identity_summary_en?: string | null
}): LocalizedPersonaText {
  if (getLocale() === 'zh') {
    return { archetype: p.archetype, identity_summary: p.identity_summary }
  }
  const pick = (en: string | null | undefined, field: string): string => {
    if (en) return en
    console.error(
      `[i18n/catalog] 人格缺 en-US overlay 的 ${field}，src/personas/en-US/ 需要补一条：`,
      p.id,
    )
    return missingMarker(`persona.${p.id}.${field}`, getLocale())
  }
  return {
    archetype: pick(p.archetype_en, 'archetype'),
    identity_summary: pick(p.identity_summary_en, 'identity_summary'),
  }
}

/* ================================================================== *
 * §E 立场标签（stance_enum 的显示层）
 *
 * `stance_enum` 的值是 wire contract：引擎按它给立场分桶，后端 parity 测试
 * 逐字保护（契约 12.2）。所以英文**不是翻译它**，而是后端另发一列只用来显示的
 * `stance_labels_en`，与 stance_enum 逐位对应——位置即契约，后端 catalog_en.py
 * 在 import 期断言两列等长，对不上后端直接起不来。
 *
 * 为什么不进 key 表：中文标签就等于 wire 值本身，写进资源文件会被 i18n-gen 的
 * wire 黑名单当场拦下；只给英文写一份则是给同一批标签立第二个 owner
 * （D5 要防的正是"同一个东西在两个页面两个名字"）。
 * ================================================================== */

/**
 * 一行任务类型的立场标签，按当前 ui_lang 取好，顺序与 stance_enum 一致。
 *
 * 返回 {value, label}：`value` 恒是 wire 值（做 key、做上行参数都用它），
 * `label` 才是画到屏幕上的。分开返回是为了让调用点不可能把 label 当 wire 用。
 */
export function localizeStanceLabels(row: {
  task_type: string
  stance_enum: string[]
  stance_labels_en?: string[]
}): ReadonlyArray<{ value: string; label: string }> {
  const wire = row.stance_enum
  if (getLocale() === 'zh') return wire.map((v) => ({ value: v, label: v }))

  const en = row.stance_labels_en
  // 长度对不上就整行标缺口，而不是逐位 en[i] ?? 中文兜底：位置即契约，
  // 错位的表现是"每个标签都显示成了另一个立场的名字"——比缺译更难发现。
  if (!en || en.length !== wire.length) {
    console.error(
      '[i18n/catalog] stance_labels_en 缺失或与 stance_enum 不等长，后端目录需要修：',
      row.task_type,
      { stance_enum: wire.length, stance_labels_en: en?.length },
    )
    return wire.map((v) => ({
      value: v,
      label: missingMarker(`stance.${row.task_type}.${v}`, getLocale()),
    }))
  }
  return wire.map((v, i) => ({ value: v, label: en[i] }))
}
