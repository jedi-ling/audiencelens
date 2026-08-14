/**
 * 使用教程页（TutorialPage.tsx）。owner: agent 7。
 *
 * ⚠ 这里**没有**任务类型名与材料字段名。
 * 页面底部那张「任务类型材料需求」表读的是 mock-data 的 TASK_TYPES.name 与
 * TASK_MATERIALS[].label，它们是目录数据：英文侧的事实源是 catalog.* overlay
 * （契约 D5/D6），不是本文件。在这里另写一份翻译，教程页与创建评审页就会显示
 * 两套字段名，而用户照着教程去表单里找那个字段会找不到。
 *
 * 同理，材料字段的中文 key（TASK_MATERIALS[].key）是 wire contract，永不进 key 表。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '使用教程',
  'header.title': '使用教程',
  'header.subtitle': '了解 AudienceLens 评审系统的完整流程与材料要求',

  // ---- 评审流程总览 ----
  'flow.title': '评审流程总览',
  'flow.desc': '上传文件 → AI 提取 → 编辑确认 → 启动评审',
  // 序号是渲染时算的（i + 1），不是四条各写一遍——四步的措辞一致，只有数字不同。
  'flow.step': 'Step {{n}}',

  'step_select_type.label': '选择任务类型',
  'step_select_type.desc': '根据评审目标选择对应的任务类型',
  'step_upload.label': '上传文件',
  'step_upload.desc': '上传任意文档，AI 自动提取结构化材料',
  'step_edit.label': '编辑材料',
  'step_edit.desc': '检查 AI 提取结果，手动修改补充',
  'step_panel.label': '选择角色并启动',
  'step_panel.desc': '选择角色包，启动评审查看报告',

  // ---- 上传文件，AI 自动提取 ----
  'upload.title': '上传文件，AI 自动提取',
  'upload.desc': '核心流程：上传文档 → AI 阅读提取 → 你来编辑确认',
  'upload.hint':
    'AI 提取完成后，所有字段均可手动修改。你可以补充 AI 遗漏的信息、修正不准确的内容、或添加额外说明。最终提交的内容以你的编辑为准。',

  /** 三种上传方式共用的「推荐」角标，按 highlight 决定渲不渲染。 */
  'method.badge': '推荐',

  'method_file.title': '文件上传（推荐）',
  'method_file.desc': '上传任意文档，AI 自动阅读并提取结构化材料',
  // 这四条是「文件上传」下面的要点，各自一个块：一个块里放不下四个 hint。
  'method_file_formats.hint': '支持 .txt .md .json .pdf .docx（旧版 .doc 需先另存为 .docx）',
  'method_file_autofill.hint': 'AI 阅读文档后自动填充所有字段',
  'method_file_editable.hint': '提取完成后可手动修改每个字段',
  'method_file_any_doc.hint': 'GDD、设计文档、开发日志等均可直接上传',

  'method_example.title': '示例导入',
  'method_example.desc': '一键导入预设示例数据，快速体验评审流程',
  // 示例数量来自后端 /api/examples。拿不到数量时用不含数字的说法，
  // 不给占位数假装知道——这两条是同一句话的两个分支，所以同属 count 块。
  'count.with_number': '{{count}} 个预设示例覆盖多种任务类型',
  'count.unknown': '预设示例覆盖多种任务类型',
  'method_example_first_use.hint': '适合首次使用时了解系统功能',

  'method_manual.title': '手动填写',
  'method_manual.desc': '根据任务类型自动生成结构化表单，逐项填写',
  'method_manual_fields.hint': '每个任务类型有专属的必填/选填字段',
  'method_manual_when.hint': '适合材料较少或需要精确控制内容的场景',

  // ---- 适合上传的文件类型 ----
  'filetypes.title': '适合上传的文件类型',
  'filetypes.desc': '任何包含游戏相关信息的文档都可以上传',
  'filetype_gdd.title': '游戏设计文档 (GDD)',
  'filetype_gdd.desc': '包含核心循环、系统设计、角色设定等',
  'filetype_devlog.title': '开发日志 / 更新说明',
  'filetype_devlog.desc': '版本更新内容、开发进度、路线图',
  'filetype_store.title': 'Steam / 商店页文案',
  'filetype_store.desc': '游戏描述、标签、截图说明、定价信息',
  'filetype_crowdfunding.title': '众筹页面内容',
  'filetype_crowdfunding.desc': '项目介绍、回报层级、团队信息',
  'filetype_community.title': '社区运营文档',
  'filetype_community.desc': 'Discord 频道规划、社区策略、活动计划',
  'filetype_localization.title': '本地化翻译文件',
  'filetype_localization.desc': '翻译样本、文化适配说明、UI 适配问题',
  // 体积上限由 formatBytes 格式化后插进来，所以这里没有硬编码的 MB。
  // 扩展名清单来自 /api/upload-config，接口拿不到时整句不渲染（不能编一份白名单）。
  'limits.hint':
    '系统实际接受的文件格式：文本类 {{text_ext}}（单个文件不超过 {{text_max}}），图片类 {{image_ext}}（单张不超过 {{image_max}}）。其他格式的文档请先转换为以上格式再上传。',

  // ---- 任务类型材料需求 ----
  'materials.title': '任务类型材料需求',
  'materials.desc': 'AI 会根据任务类型自动提取对应字段，你也可以手动补充',
  'materials_task_type.label': '任务类型',
  'materials_required.label': '必填字段',
  'materials_optional.label': '选填字段',

  // ---- 评审结果说明 ----
  'results.title': '评审结果说明',
  'results.desc': '评审报告包含以下核心内容',
  'result_risk.label': '风险等级',
  'result_risk.desc': '绿/黄/橙/红 四级风险评估',
  'result_stance.label': '立场分布',
  'result_stance.desc': '各角色的立场取向（具体档位由任务类型决定）',
  'result_issues.label': '优先问题列表',
  'result_issues.desc': '按严重程度排序的关键问题',
  'result_persona.label': '每个角色的详细视角',
  'result_persona.desc': '各角色的独立评审观点',
  'result_calibration.label': '校准指标',
  'result_calibration.desc': '一致性、覆盖率、幻觉率等质量指标',

  'start.cta': '开始创建评审',
} satisfies Messages
