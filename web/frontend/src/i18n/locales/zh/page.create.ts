/**
 * 新建评审向导（6 步）。owner: agent 4（CreateReviewPage.tsx）。
 *
 * 动手前必须知道的三条边界：
 *
 * 1. **材料字段的 label / placeholder 不在这里。** 它们是 TASK_MATERIALS 的数据，
 *    按契约 D5 / D6 归 catalog.material overlay（owner: batch-0），mock-data.ts 源行
 *    一个字不改。本文件里只有 generic_field.* 那一组，因为那组是本页自己造的兜底字段，
 *    TASK_MATERIALS 里根本没有它。
 *
 * 2. **提交时 materials[].type 发的是中文 wire key**（'一句话pitch' / '核心循环说明' …）。
 *    它们是协议字段不是文案，永不进 key 表——翻了之后编译通过、界面正常、评审照跑 200，
 *    只是引擎再也提取不到材料（契约 12.2）。generic_field 那一组的 key 同理，
 *    只有它的 label / placeholder 是文案。
 *
 * 3. 评审模式的三个档位名（快速 / 标准 / 完整）**不在这里**，读 enum.mode_badge.*
 *    ——ReviewMode 是后端枚举，按契约 §11 第 3 条一律走 enum.*。
 *    本文件只有 mode_name.value 那半句「…模式」的包装，因为中英文语序不同，
 *    把它拼进枚举值会锁死英文语序。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '新建评审',

  // ---- 顶部步骤指示器。stage 是变体块：块内叶子是"哪一步"，不是角色 ----
  'stage.skill': '选择技能',
  'stage.task_type': '选择任务类型',
  'stage.material': '上传材料',
  'stage.persona': '选择角色',
  'stage.option': '评审选项',
  'stage.confirm': '确认并启动',

  // ---- 第 0 步：技能 ----
  'skill.title': '选择评审技能',
  'skill.desc': '不同技能对应不同的评审视角和侧重点',
  /** 老链接带着 persona_generate 这类不能创建评审的技能进来时的提示。 */
  'dropped_skill.title': '「{{skill}}」还不能用来创建评审',
  'dropped_skill.desc':
    '它目前不会改变评审的跑法，选了也等于没选，所以这里没有替你选上。请另选一个技能。',
  /** tApiError 的 fallbackKey：/api/skills 挂了、且抛的不是 ApiError 时用它。 */
  'skill_list.error': '加载技能列表失败',
  'skill_error.title': '技能列表没能加载出来',
  // 不用 common.action.retry（"重试"）：这里重来的是一次列表加载，不是重试一个失败的动作。
  'skill_error.cta': '重新加载',
  'skill_list.empty': '当前账号下没有可用于创建评审的技能。',
  /** 只在后端真的声明了 task_types 时才报数——没声明不显示，不拿 0 充数。 */
  'skill_card.meta': '{{count}} 种任务',

  // ---- 第 1 步：任务类型 ----
  'task_type.title': '选择任务类型',
  'task_type.desc': '选择你要评审的内容类型',
  // 下面两条与上面一条是同一句副标题的三个互斥分支，用块名区分而不是靠角色段。
  // 只有后端真的声明了 task_types 才说"该技能声明支持的类型"，否则就是在替后端
  // 发明一条它没有的限制。
  'task_type_scoped.desc': '当前技能：{{skill}} · 以下为该技能声明支持的任务类型',
  'task_type_open.desc': '当前技能：{{skill}} · 它没有限定任务类型，下面全部可选',
  /** 分类筛选里的"全部"。其余分类名来自 TASK_TYPE_CATEGORIES（目录数据，不归本文件）。 */
  'category_all.tab': '全部',

  // ---- 评审模式（第 1 步下半 + 第 3、5 步的回显） ----
  'mode.title': '评审模式',
  /**
   * "快速模式" / "Quick mode"。第 3 步与第 5 步都用它，同一句话同一个 owner，不重复抽。
   * 档位名（快速 / 标准 / 完整）不在这里——它是后端枚举 ReviewMode 的标签，
   * 读 enum.mode_badge.*（契约 §11 第 3 条）。
   */
  'mode_name.value': '{{mode}}模式',
  // range 是 "3" 或 "4-6" 这种已经拼好的区间串，不是数字，所以不挂复数。
  'mode_card.unit': '{{range}} 人',
  'feature_cross_exam.badge': '交叉质询',
  'feature_calibration.badge': '校准检查',
  'feature_none.badge': '无额外步骤',

  // ---- 第 2 步：材料 ----
  'material.title': '上传评审材料',
  'material.desc': '手动填写文本，或上传文件让 AI 自动提取材料',
  'input_mode_text.tab': '文本输入',
  'input_mode_file.tab': '文件上传',
  'dropzone.cta': '拖拽文件到此处，或<click>点击上传</click>',
  'dropzone.hint': '支持 .txt .md .json .pdf .docx（不支持旧版 .doc）· AI 自动提取结构化材料',
  'extract.pending': 'AI 正在阅读文件并提取材料...',
  'extract.hint': '请稍候，通常需要 5-10 秒',
  /**
   * 提取失败。reason 由 tApiErrorParts 给：中文界面拿到的是后端原文
   * （后端会说清是文件太大 / 格式不支持 / 没配 key / 限流，这些用户改一下就能过），
   * 英文界面拿到的是按 code 出的前端译文，后端中文原文降级进 title 属性。
   * 一律替换成"AI 提取失败"会让用户以为是模型不行，于是放弃这个功能。
   */
  'extract.error': 'AI 提取失败：{{reason}}。你也可以直接手动填写下面的材料字段。',
  'extract_reason_unknown.error': '未知原因',
  'extract.success': '已提取 {{count}} 个字段 · 可在下方编辑修改',
  'examples.cta': '快速开始：导入示例数据',
  'target.label': '评审目标',
  'target.placeholder': '例如：《星际漂流》概念设计文档',
  'fields.title': '编辑材料详情',
  'fields.hint': 'AI 已提取 {{count}} 个字段，请检查并修改',
  /**
   * GENERIC_MATERIAL_FIELD 的文案。任务类型在 TASK_MATERIALS 里没有字段定义时的兜底，
   * 只有这一组材料文案属于本页——其余都在 catalog.material overlay 里。
   * 它的 wire key（'材料正文'）在 tsx 里写死，不在这里。
   */
  'generic_field.label': '材料正文',
  'generic_field.placeholder':
    '粘贴要评审的材料全文（这个任务类型还没有配置分项字段，先整段贴进来）...',
  /** AI 从文件里提取出来、但当前任务类型没有对应字段的那些键。 */
  'extra_fields.desc':
    '以下内容是从文件里提取出来的，不属于「{{taskType}}」的标准字段，但会一并提交给评审员。不需要的话清空即可。',
  /** 任务类型在 TASK_TYPES 里查不到时，上面那句里 {{taskType}} 的替代说法。 */
  'extra_fields_unknown.label': '当前任务类型',

  // ---- 第 3 步：角色 ----
  'persona.title': '选择角色包',
  'persona.desc': '选择一个角色包快速填充，或手动选择角色',
  'mode_summary.title': '当前评审模式',
  'mode_summary.unit': '· {{range}} 个角色',
  'pack_card.unit': '{{count}} 个角色',
  'pack_intro.desc': '<name>{{name}}</name>：{{desc}}',
  'persona_list.title': '角色列表',
  'persona_list.meta': '已选择 {{count}} / 上限 {{max}} 个',
  /** 会被后端 select_panel_by_mode 静默改写的两种组合，在提交前就说清楚。 */
  'pack_conflict.title': '不能跨角色包混选（当前混了 {{count}} 个包：{{packs}}）',
  'pack_conflict.desc':
    '一次评审只能使用同一个角色包内的角色，跨包选择时只会保留其中一个包。请只保留同一包内的角色，或直接点上面的角色包一键选择。',
  /** 上面那句里包名列表的分隔符。中文用顿号，英文用逗号加空格——所以它必须是一条 key。 */
  'pack_conflict.value': '、',
  'over_max.title': '超出「{{mode}}模式」的角色上限（{{max}} 位）',
  // 一句话里两个计数，复数只能挂一个（ICU 同限制）。这里挂"要取消几位"。
  'over_max.desc':
    '当前模式最多支持 {{max}} 位评审员，请取消 {{count}} 位，或回到「任务类型」步骤选择人数上限更高的模式。',

  // ---- 第 4 步：评审选项 ----
  'option.title': '评审选项',
  'option.desc': '配置评审的附加功能',

  /* 两层评审开关。文案说清"多花什么、换来什么"——它比常规评审多一轮
     廉价档调用，该由用户显式选择而不是替他决定花这笔钱。 */
  'wide_screen.label': '两层评审（全包初筛 → 深评）',
  'wide_screen.desc':
    '先让所选人格包**每一位**人格用一次廉价短调用过一遍材料（只出立场、严重度和一句话关切），再按分歧信号选出进入完整评审的面板。不开启时按预设顺序直接取前几位。',
  'wide_screen.hint':
    '会多一轮廉价档模型调用（成本远低于完整评审，报告里单独列出）。谁晋级、为什么，报告的「初筛记录」里逐条可查。显式点名人格时本层自动跳过——你指定的角色一个都不会被筛掉。',
  'evaluation.label': '启用评估报告',
  // 维度个数取自 EVALUATION_DIMENSIONS，不写死——写死的数会在后端加减维度时变成假数。
  'evaluation.desc': '评审完成后自动运行 {{count}} 维度评估，生成评分卡和伦理报告。',
  'red_team.label': '启用红队对抗',
  'red_team.desc':
    '标准评审完成后，自动启动红队对抗模式，用对抗性视角主动攻击产品弱点，模拟最挑剔的用户和恶意场景，暴露隐藏风险。',
  'red_team_case_pricing.badge': '付费模型压力测试',
  'red_team_case_community.badge': '社区危机预演',
  'red_team_case_localization.badge': '本地化文化风险',
  'red_team_case_pr.badge': '公关危机模拟',

  // ---- 第 5 步：确认 ----
  'confirm.title': '确认评审配置',
  'confirm.desc': '检查以下信息，确认无误后启动评审',
  'confirm_skill.title': '评审技能',
  'confirm_task_type.title': '任务类型',
  'confirm_mode.title': '评审模式',
  'confirm_target.title': '评审目标',
  'confirm_target.empty': '未填写',
  'confirm_material.title': '评审材料',
  // 分母把"额外字段"也算进去，否则会出现"已填 5 / 共 3 项"。
  'confirm_material.meta': '<filled>{{count}}</filled> / {{total}} 项已填写',
  /** 材料清单里每一行的字段名。冒号在中英文里不是同一个字符，所以它进 key 表。 */
  'confirm_field.label': '{{name}}：',
  'confirm_field.empty': '未填写',
  'confirm_persona.title': '已选角色 ({{count}})',
  'confirm_persona.meta': '· 角色包：{{pack}}',
  'confirm_extra.title': '附加功能',
  'confirm_extra_evaluation.badge': '评估报告',
  'confirm_extra_red_team.badge': '红队对抗',
  'cost.title': '成本',
  // 这里刻意不给"预估成本"：真实成本由实际 token 数 × 模型定价决定，发起前谁都不知道。
  'cost.desc':
    '实际成本取决于材料长度、角色数量和所用模型，发起前无法准确预估。评审跑完后，报告页与评审记录里会显示这次真实消耗的 token 与费用。',

  // ---- 底部操作区 ----
  // "上一步 / 下一步"用 common.action.prev / .next（契约 §11 第 2 条），不在这里重抽。
  'launch.cta': '🚀 启动评审',
  /** tApiError 的 fallbackKey。 */
  'launch.error': '发起评审失败',
  'launch_pack_mismatch.error': '所选角色与角色包/评审模式不一致，请返回第 3 步调整后再启动',
  'launch_no_material.error': '还没有填写任何评审材料，请返回第 2 步补充后再启动',
} satisfies Messages
