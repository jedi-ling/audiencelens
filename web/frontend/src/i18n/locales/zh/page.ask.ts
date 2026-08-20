/**
 * 对话评审页（/ask）。owner: agent-2。
 *
 * ── 三类**故意留在 AskPage.tsx 里的中文**，不是漏抽（调用点逐条写了理由）──
 *
 * 1. engine-prompt。`pickCandidate` 的「就是{任务类型}」与纯图消息的
 *    「（仅附图，无文字说明）」会作为**用户消息**发给后端做意图解析，而后端那一档
 *    是中文关键词打分：发英文 → 命中数归零 → 静默退化到默认任务类型，用户点了
 *    「Steam 商店页」却跑出概念评审，且不报错。见契约 12.2。
 *
 * 2. 目录文案。`TASK_LABELS` / `SKILL_LABELS` 是任务类型与技能的展示名，它们的
 *    英文事实源在后端 `catalog.en-US.json`，前端那份 overlay 由
 *    `npm run i18n:sync-catalog` 生成、**不许手写**（契约 D5）。抄一份进这里
 *    就是给同一批文案造了第二个 owner，表现是「同一个任务类型在两个页面显示
 *    两个英文名」。
 *
 * 3. 枚举标签。`RISK_BADGE` 的四档发布风险属 `enum.release_risk.*`，
 *    owner 是 batch-0（契约 4.3 / §3.4 例 7）。同理 `evidence_quality`、
 *    `mode`、`persona_pack`、`primary_stance` 都是后端枚举原值，这里只提供
 *    包在它们外面的框架文案（「证据 · {{quality}}」），值本身不进本文件。
 *
 * ── 另外两条本文件内部的规矩 ──
 *
 * · 连接状态那四条提示（sync_failed / realtime_unavailable / realtime_reconnecting /
 *   stalled）**刻意不与 `page.progress.*` 合并**：两页语气不同是有意的（契约 D10）。
 * · 带 {{count}} 的 key 调用方只写逻辑 key，`_one/_other` 由运行时选（契约 D9）。
 */
import type { Messages } from '@/i18n/types'

export default {
  // ---- 页面骨架 ----
  'meta.title': '对话评审',
  'header.title': '对话评审',
  'header.desc': '描述你要评审的内容，剩下的交给评审团',
  'sidebar_collapse.aria': '收起历史侧栏',
  'sidebar_collapse.tooltip': '收起历史侧栏',
  'sidebar_expand.aria': '展开历史侧栏',
  'sidebar_expand.tooltip': '展开历史侧栏',

  // ---- 开场白与示例 ----
  'greeting.value': '你好，说说你想评审什么——一个页面、一份文案、一个产品概念都可以。',
  // 原文就是这四个字。集成期从"试试从这些示例开始"改回来：本期只做 i18n，
  // 改文案属于顺手优化（契约 12.3），而且 AskPage 里那段讲可读性的注释
  // 逐字引用了"从一句话开始"，改了文案注释就对不上了。
  'examples.title': '从一句话开始',
  'examples.hint': '也可以直接在下方输入框描述你要评审的内容',

  /* ---------------- 待验证追踪卡 ----------------
     判断飞轮在首页的落点：欠着回填的预测按项目分组，摆在发起评审的主路径上。
     hint 那句说的是真实机制（project_memory_service 按回填结果过滤），不是话术。 */
  'tracking.title': '{{count}} 条预测待验证',
  'tracking.meta': '{{count}} 条未回填 · 最早已留档 {{days}} 天',
  'tracking.hint': '回填结果会直接影响下一次评审：被真人测试推翻的判断不再进入同项目的评审上下文。',
  'tracking_unnamed.label': '未命名项目',
  /** 列表被 200 条上限截断时的标题：总数是下界不是准数，必须带 +。
      变量名用 total 不用 count：这条没有单复数分支，count 会触发复数变体检查。 */
  'tracking_more.title': '{{total}}+ 条预测待验证',
  /* 确认卡回填提醒:说的是真实机制(项目记忆按回填结果过滤),不是催办话术 */
  'verify_nudge.hint': '该项目还有 {{total}} 条预测未回填——先回填,本次评审就不会复读已被推翻的判断。',
  'verify_nudge.cta': '去回填',

  /* 对话链路的高级选项（确认卡上的 chip）。与向导第 4 步同一批开关，
     文案更短：这里空间紧张，完整解释靠 tooltip。 */
  'advanced.label': '高级',
  'wide_screen.badge': '两层评审',
  'wide_screen.tooltip':
    '全包每位人格先用一次廉价短调用过一遍材料，再按分歧信号选出进入完整评审的面板。会多一轮廉价档调用，报告里单独列出。',
  'adaptive.badge': '自适应面板',
  'adaptive.tooltip':
    '先跑小面板，再按边际价值逐个扩面，低于阈值就停，不把档位人数跑满。扩面分数是可解释的启发式，不是实测信息增益。',
  'examples.cta': '试试这些例子',
  /* 这三条既是展示文案，也是点一下就**当作用户消息发出去**的内容。
     所以英文侧不是逐字直译，而是写英文用户真会打出来的那句话。 */
  'example_pricing.value': '帮我评审一下这个产品的定价页，用户会不会觉得贵',
  'example_onboarding.value': '这是我们的新手引导流程，看看用户会不会中途放弃',
  'example_pitch.value': '这是我的创业项目申报表，帮我用投资人的眼光过一遍',

  // ---- 未配置 Key 的软拦横幅 ----
  'no_key.title': '请先配置 API Key',
  'no_key.desc': '评审需要调用真实模型，未配置 Key 无法开始。',
  'no_key.cta': '去设置页填写',

  // ---- 附件：拖拽、预览、随消息发送 ----
  'drop.hint': '松开以上传截图/文件',
  'attach.hint': '支持拖拽文件到对话区，或 Ctrl+V 粘贴截图',
  'attachment_preview.tooltip': '点击放大预览',
  'attachment_remove.aria': '移除 {{filename}}',
  'attachment_image.aria': '附图 {{index}}',
  'attachment_note_review.hint': '{{count}} 张图片将随评审一起发送给支持视觉的模型',
  'attachment_note_follow_up.hint': '{{count}} 张图片将随追问一起发送给支持视觉的模型',
  'attachment_limit.error': '最多附带 {{count}} 张图片——先移除几张再继续上传',
  'preview_close.aria': '关闭预览',

  // ---- 输入区 ----
  'upload.aria': '上传截图或文件',
  'upload.tooltip': '上传截图 / demo 图 / 文件（图片会作为多模态材料让模型直接看）',
  'upload.error': '「{{filename}}」上传失败：{{detail}}',
  'skill_picker.aria': '选择技能',
  'skill_picker.tooltip': '选技能——不用等 AI 猜，直接指定评审视角',
  'skill_quota.badge': '剩 {{count}} 次免费',
  'skill_quota.empty': '免费次数已用完',
  // 配额没取到时如实交代，而不是让「没数字」看上去等于「不受限」。
  'skill_quota.hint': '剩余免费次数暂时没取到。技能仍可选用，实际是否计次以创建评审时后端判定为准。',
  'type_picker.aria': '选择评审类型',
  'type_picker.tooltip': '选评审类型——直接指定，不用等 AI 猜',
  'type_picker.placeholder': '搜索评审类型…',
  'input.aria': '评审输入',
  'input.placeholder': '说说你想评审什么…（Enter 发送，Shift+Enter 换行）',
  'input_follow_up.placeholder': '问问{{label}}…（Enter 发送）',
  'send.aria': '发送',

  // ---- 钉住的技能 / 类型 / 项目 ----
  'pinned_skill.badge': '技能 · {{name}}',
  'pinned_skill.aria': '取消技能',
  'pinned_type.badge': '类型 · {{name}}',
  'pinned_type.aria': '取消类型',
  'pinned_project.badge': '项目 · {{name}}',
  'pinned_project.aria': '移出项目',
  'pinned_project.tooltip': '移回未分组',
  'project_select.aria': '移到项目',
  'project_select.placeholder': '移到项目…',
  'project_select.empty': '还没有项目，去侧栏新建一个',

  // ---- 追问模式 ----
  'follow_up.badge': '正在追问 · {{label}}',
  'follow_up.label': '这份报告',
  'follow_up.cta': '追问',
  'follow_up.tooltip': '就在这条对话里继续追问，不用打开报告',
  'follow_up.error': '追问失败，请再试一次',
  'follow_up_exit.aria': '退出追问模式',
  'follow_up_report.cta': '追问这份报告',

  // ---- 侧栏：对话树与项目 ----
  'new_conversation.cta': '新建对话',
  'new_project.cta': '新建项目',
  'new_project.confirm': '创建',
  'new_project.placeholder': '给项目起个名字…',
  'projects.loading': '加载项目…',
  'project.empty': '把对话拖到这里',
  'conversation_untitled.label': '未命名对话',
  'ungrouped.title': '未分组',
  'ungrouped.empty': '没有未分组的对话',
  'legacy.title': '早期评审记录',
  // 空列表有两种完全不同的含义，必须分开说：「你还没做过评审」vs
  //「这台实例上历史要登录才看得到」。后者说成前者，用户会以为自己的评审丢了。
  'login_required.title': '登录后可以看到自己的评审历史',
  'login_required.desc': '未登录时的评审不会归到任何账号下',
  'login_required.cta': '去登录',
  'sidebar_empty.title': '还没有对话或评审记录',
  'sidebar_empty.desc': '开始一段新对话，它会出现在这里',

  // ---- 侧栏：改名 / 删除 / 拖拽的结果与二次确认 ----
  'project_rename.aria': '重命名「{{name}}」',
  'project_rename.tooltip': '重命名',
  'project_delete.aria': '删除「{{name}}」',
  'project_delete.tooltip': '删除项目（对话会回到未分组）',
  'project_delete_confirm.aria': '确认删除项目「{{name}}」',
  'project_delete_confirm.confirm':
    '删除项目「<name>{{name}}</name>」？<br/>里面 {{count}} 段对话会回到"未分组"，不会被删除。',
  'project_delete_confirm.cta': '删除项目',
  'review_delete.aria': '删除「{{title}}」',
  'review_delete.tooltip': '删除这条评审（会二次确认）',
  'review_delete_confirm.aria': '确认删除「{{title}}」',
  'review_delete_confirm.confirm':
    '删除「<name>{{title}}</name>」？<br/>报告、各角色意见、全部追问记录一起没，无法撤销。',

  // ---- 失败态（都经 tApiError，后端有更具体的话就用后端的）----
  'history.error': '加载失败',
  'history_delete.error': '删除失败：{{detail}}',
  'history_delete.hint': '请检查网络后重试',
  'project_create.error': '创建项目失败',
  'project_rename.error': '重命名失败',
  'project_delete.error': '删除项目失败',
  'conversation_move.error': '移动对话失败',
  'parse.error': '解析失败，请再说一次',
  'create.error': '发起评审失败',
  'need_key.cta': '去填写 API Key',

  // ---- 落库用的消息文本 ----
  // 这三条会写进对话记录（服务端），重放时按原样显示——**它们的语言在写入
  // 那一刻就冻结了**，之后用户切界面语言不会改写历史记录，同报告正文的规矩
  //（契约 8.6：显示原文，不机翻）。
  'persisted_review.value': '[评审已创建]',
  'persisted_confirm.value': '[确认评审方案：{{taskType}}]',
  'persisted_confirm.empty': '未定',
  'restored_review.label': '（历史评审）',

  // ---- 意图解析结果 ----
  'clarify.hint': '能再说得具体一点吗？',
  'confirm.label': '我明白了，你想做的是',
  'mode.badge': '深度 · {{mode}}',
  'pack.badge': '评审团 · {{pack}}',
  'skill.badge': '技能 · {{name}}',
  'project.badge': '项目 · {{name}}',
  'personas.label': '指定角色（点 × 可移除，移除全部则回到自动选人）',
  'persona_restore.aria': '恢复 {{name}}',
  'persona_restore.tooltip': '点击恢复',
  'persona_remove.aria': '移除 {{name}}',
  'persona_remove.tooltip': '点击移除',
  'confidence.label': '匹配把握',
  'confidence.value': '{{level}}（{{percent}}）',
  'confidence_high.label': '高',
  'confidence_medium.label': '中',
  'confidence_low.label': '偏低',
  'rule_parse.hint': '未配置 API Key，本次为规则解析，任务类型可能判得不准——填 Key 后用模型解析会更靠谱。',
  'submit.cta': '开庭评审 →',
  'submit.pending': '开庭中…',
  // res.skill_degraded 是后端给的中文自由文本（不是 code），原样插进来。
  // 英文界面上它会保持中文——这一条记在交付报告里，真解在后端补稳定 code。
  'skill_degraded.value': '{{reason}}。想继续用可以兑换 CDK，或在设置页填写自己的 API Key（BYOK 不受此限制）。',

  // ---- 评审卡片：进度与连接交代 ----
  'progress.pending': '评审团正在评审中…',
  'progress.hint': '跑完之前你可以继续在这聊别的，我不会打断你。',
  // 一个不动的进度条必须配一句话，否则用户只会读成「卡死了」。
  'sync_failed.error': '无法同步评审进度（已连续失败 {{count}} 次），正在自动重试。评审在后台继续跑，不会因此中断。',
  'realtime_unavailable.hint': '实时连接不可用，已改为每 {{seconds}} 秒主动同步一次进度。进度仍会更新，只是稍慢。',
  'realtime_reconnecting.hint': '实时连接中断，正在重连；期间改用轮询同步进度。',
  'stalled.hint': '已有 {{idle}} 秒没有新进展 —— 仍在处理中（某个人格的长文本推理可能比较久），每 {{seconds}} 秒会主动同步一次状态。',
  'review_failed.title': '评审失败了',
  'review_failed.error': '评审失败',

  // ---- 评审卡片：报告摘要 ----
  'report_card.title': '评审报告',
  'report_card.loading': '读取报告中…',
  // 读不到就说读不到：0 值行看起来跟正常结果一模一样，不能拿它冒充结论。
  'report_card.empty': '报告内容为空（没读到角色意见）',
  'report_card.cta': '查看完整报告',
  'count.fixes': '{{count}} 条修复项',
  'count.personas': '{{count}} 位角色',
  'token.tooltip': '输入 {{input}} · 输出 {{output}} token',
  'token.unit': '{{value}} tok',
  'cost.value': '花费 {{amount}}',

  // ---- 报告弹窗 ----
  'report_modal.subtitle': '完整报告',
  'conclusion.title': '结论',
  'evidence.badge': '证据 · {{quality}}',
  'count.priority_fixes': '优先修复项 · {{count}}',
  'fix.hint': '建议：{{text}}',
  'count.persona_notes': '角色简报 · {{count}}',
  // 前导空格与分隔符是这条消息的一部分：它接在立场词后面，怎么接是语言相关的。
  'count.issues': ' · {{count}} 条意见',
  'stance.empty': '未表态',
  // 后端没给这位角色的立场。用破折号占位而不是留空——留空看起来像渲染坏了。
  'stance_row.empty': '—',
  'persona_chat.cta': '跟TA聊聊',
  'count.disagreements': '主要分歧 · {{count}}',
  'disagreement_stance.value': '{{persona}}：{{stance}}',
  'disagreement_evidence.value': '（{{evidence}}）',
  'disagreement.hint': '调解建议：{{text}}',
  'count.information_gaps': '信息缺口 · {{count}}',

  // ---- 匿名体验版的截断提示 ----
  'gated.hint': '还有 {{count}} 字被隐藏',
  'gated.cta': '登录看完整回答',
} satisfies Messages
