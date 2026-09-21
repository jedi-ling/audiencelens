/**
 * 评审报告页。owner: agent-1（src/pages/ReportPage.tsx）。
 *
 * 全站最大的一份语料。三件事在动手前先说清楚，否则后来的人会按错误的口径改：
 *
 * 1. **这里只有前端文案。** 报告正文里绝大多数字（primary_stance、
 *    primary_recommendation、issue、why_it_matters、evidence、topic、
 *    引擎的 limitation / notice / simulation_notice…）都是引擎或后端产出的
 *    自由文本，它们是**产出物**不是界面文案，语言在评审入队那一刻就冻结了
 *    （契约 §0 的 report_lang）。翻译它们等于伪造证据，一个字都不许动。
 *    界面语言与正文语言不一致时的正确做法是显示语言横幅，不是机翻（契约 8.6）。
 *
 * 2. **枚举只做浅层映射。** 后端枚举值（release_risk / evidence_quality /
 *    gate_reason / stop_reason…）的标签在 enum.* 里，这里不重复一份。
 *    认不出的枚举值不静默兜底成某一档，也不把后端英文键当标签直出——
 *    显式渲染「未知 X（原值）」，见下面的 *.label / *_unknown.* 几条。
 *
 * 3. **导出件也是一份报告。** md_* 那一批是 generateMarkdown() 拼的
 *    Markdown 导出件用的，它不在 JSX 里，按"渲染到界面"的口径扫描会整批漏掉。
 *    ETHICS.md 的两条强制项（Synthetic Banner、Limitations & Caveats）
 *    在导出件里同样必须出现，md_banner.* 与 limitation_* 就是为此存在的。
 */
import type { Messages } from '@/i18n/types'

export default {
  /* ---------------- 页面框架 ---------------- */
  'meta.title': '评审报告',
  'header.title': '评审报告',
  /** 标题下面那行小字。与 header.title 同字不同角色，改版时会各自变。 */
  'header.subtitle': '评审报告',
  /** {{mode}} 来自 enum.mode_badge.*。中文是后缀、英文是后缀位置不同，所以不拼死。 */
  'header.badge': '{{mode}}模式',
  'body.loading': '加载报告中…',
  'pending.title': '报告尚未生成',
  'pending.desc': '评审可能还在跑，也可能还没开始——去详情页看实时进度。',
  'pending.cta': '查看进度',

  /* ---------------- 反复出现的链接 ---------------- */
  'link_detail.cta': '查看评审详情',
  'link_new_review.cta': '重新发起评审',
  'link_login.cta': '登录 / 注册',

  /**
   * 列表连接符。
   *
   * 中文用顿号、英文用逗号加空格——`join('、')` 写死在 tsx 里的话，
   * 英文界面会出现「Emily、Marcus」这种没人会写的东西。
   * 中点分隔符（' · '）与斜杠不进这里：它们两种语言里写法相同。
   */
  sep_enum: '、',
  sep_semicolon: '；',
  /** 导出件里 `- 人格 id：失败原因` 那个冒号。中文全角、英文半角加空格。 */
  sep_colon: '：',

  /**
   * 后端给了一个不在已知档位里的枚举值时的显示（release_risk / evidence_quality
   * 这类"有限档位"字段共用）。
   *
   * 为什么不直接把后端原值当标签渲染：那正是契约 D8 点名的反例
   * （PersonaRadarChart 查不到轴名就把后端英文键画在雷达图上）。原值要给，
   * 但必须包在"我不认识这个档位"里，读者才知道自己看到的不是一个正常标签。
   */
  'unknown_level.value': '未知档位（{{raw}}）',

  /* ---------------- ETHICS.md 强制项：合成声明 ---------------- */
  'synthetic_banner.title': '合成评审面板：以下全部意见由 AI 人格生成，不是真实玩家/用户的反馈。',
  'synthetic_banner.desc':
    '本报告不得作为「玩家调研结果」「用户调查数据」「真实玩家意见分布」对外展示或引用。它是投入真人测试之前的预筛工具，不能替代真人 playtest 或用户访谈，也不应作为发布决策的唯一依据。',

  /* ---------------- 人格降级 ---------------- */
  'degradation.desc': '本次有 {{count}} 位人格未能完成评审，以下结论仅基于 {{succeeded}} 位人格的输出。',
  /** 引擎没回传 succeeded_count 时用这条。不写「0 位」——那是编造。 */
  'degradation_partial.desc': '本次有 {{count}} 位人格未能完成评审，以下结论仅基于剩下那部分人格的输出。',
  'degradation.label': '未完成的人格：{{names}}',

  /* ---------------- 三层校验门控 ---------------- */
  'gate.title': '有 {{count}} 位人格的输出没通过质量校验，已被排除在下面的结论之外',
  /** 后端加了新枚举而前端没跟上时用它。原值照抄出来，方便对着后端查。 */
  'gate.label': '未知失败类型（{{raw}}）',
  'gate.empty': '引擎没有回传失败类型',

  /* ---------------- 可证伪预测 ---------------- */
  'predictions.title': '可证伪预测',
  'predictions.badge': '{{count}} 条',
  'predictions.desc':
    '每条都写明了目标指标与判定标准，可以拿去做真实验证。跑完真人测试后回填结果，就能反过来校准这套面板的准确率。',
  /**
   * confidence 必须和它的口径同框出现——单独摆一个 72%，用户会当成实测置信度，
   * 而它只是合成面板的启发式权重。<emph> 里那半句是这条提示的重点，不许拆成两条 key。
   */
  'predictions.hint':
    '启发式置信度 {{pct}} —— 由合成面板规则算出，<emph>尚未经真实结果校准</emph>，不代表历史命中率',
  'prediction_metric.label': '目标指标',
  'prediction_metric.hint': '（{{direction}}）',
  'prediction_window.label': '验证窗口',
  'prediction_criterion.label': '判定标准',
  'prediction_method.label': '验证方式',

  /* ---------------- 自适应面板 ---------------- */
  'adaptive.title': '自适应面板',
  'adaptive.empty': '本次未启用。',
  /** disabled_reason 不在 enum.disabled_reason 里时用它，不把原始码当句子直出。 */
  'adaptive_reason.label': '未识别的禁用原因：{{raw}}',
  'adaptive_executed.label': '实际评审人格',
  'adaptive_saved.label': '省下的调用',
  'adaptive_initial.label': '起始面板',
  'adaptive_step.label': '{{count}} 人后',
  'adaptive_step.value': '扩入 {{persona}}',
  'adaptive_step.hint': '下一位人格',
  'adaptive_stop.label': '停止扩面',
  'adaptive.hint': '扩面分数是可解释的启发式，不是实测信息增益，其权重仍需用真实验证结果校准。',

  /* ---------------- 显式点名人格 ---------------- */
  'panel_selection.title': '你点名的人格没有全部参与本次评审',
  'panel_selection.label': '实际参与：{{names}}',

  /* ---------------- 证据构成（报告可信度记账） ----------------
     度量的是**报告自身**：结论建立在多少直接观察/推断/信息缺口之上。
     不是产品得分——合成面板给产品打综合分是假精确，给自己记账是诚实的。 */
  'evidence_profile.title': '证据构成',
  'evidence_profile.badge': '共 {{count}} 条证据',
  'evidence_profile.desc':
    '本报告的每条结论都标注了证据等级。这里是全体人格证据的构成账目——度量报告自身的可信度，不是产品得分。',
  'evidence_direct.label': '直接观察 {{count}}',
  'evidence_inferred.label': '合理推断 {{count}}',
  'evidence_gap.label': '信息缺口 {{count}}',
  'evidence_ratio.label': '推断占比 {{pct}} / 上限 {{cap}}',
  'evidence_profile.hint':
    '维度分为各人格 1-5 打分的简单均分，括号内是最低-最高分——分歧本身就是信息。刻意不做加权综合分：权重没有校准依据。维度名为输出 schema 的原始键，不翻译。',

  /* ---------------- 章节锚点导航 ---------------- */
  'nav_bar.aria': '报告章节导航',
  'nav_summary.label': '摘要',
  'nav_evidence.label': '可信度',
  'nav_fixes.label': '优先修复',
  'nav_personas.label': '圆桌',
  'nav_disagreements.label': '分歧',
  'nav_crossexam.label': '质询',
  'nav_predictions.label': '预测',

  /* ---------------- 档位边界声明 ----------------
     数字 {{n}} 来自 REVIEW_MODE_BOUNDARIES（被 parity 测试钉在引擎 cli.py 上），
     文案不手写人数。说的是"这一档包含/不包含什么"，不是催升级的营销话。 */
  'mode_boundary_quick.desc':
    '本报告为快速档：最多 {{n}} 位人格，不含交叉质询与校准检查——页面上没有「质询」一节不代表没有分歧，是这一档不跑这个环节（standard / full 档提供）。',
  'mode_boundary_standard.desc':
    '本报告为标准档：最多 {{n}} 位人格，含一轮仲裁式交叉质询；逐人格多智能体反驳与校准检查在 full 档提供。',
  'mode_boundary_full.desc':
    '本报告为完整档：最多 {{n}} 位人格，含多智能体交叉质询与校准检查，是覆盖最全的一档。',

  /* ---------------- 初筛（两层评审 L1） ----------------
     初筛意见只用于选人，不是正式评审结论——文案必须把这条边界说死。 */
  'triage.title': '初筛记录',
  'triage.badge': '全包 {{screened}} 位初筛 · {{advanced}} 位晋级深评',
  'triage.desc': '每位人格一次廉价短调用（立场+严重度+一句话关切），按分歧信号选出深评面板。初筛意见只用于选人，正式结论以各章节为准。',
  'triage.hint': '初筛阶段材料截断至 {{chars}} 字符，深评阶段读完整材料。',

  /* ---------------- 我的判断 ----------------
     留档层此前只记评审团的预测，回填后也只能回答"评审团准不准"。
     用户真正关心的是自己的判断在不在变准——所以两边都要记。 */
  'my_judgment.title': '记下你自己的判断',
  'my_judgment.desc':
    '评审团的预测已经留档。把你自己的看法也记下来，真人测试回填之后，你会同时看到「评审团准不准」和「你自己准不准」。',
  'my_judgment.confirm': '同意评审团的结论',
  'my_judgment.cta': '我有不同判断',
  'my_judgment.placeholder': '你的判断是什么？写清楚一点，日后才能被验证。',
  'my_judgment_save.cta': '保存我的判断',
  'my_judgment.success': '已记下你的判断。真人测试回来后，在「预测复盘」里回填结果。',
  'my_judgment.error': '判断内容不能为空——没有内容的判断无法被验证。',
  'my_judgment.empty': '（同意评审团的主流建议）',
  'my_confidence.label': '你的把握',
  /** 默认不预填数字：替用户填的把握度会污染校准曲线。 */
  'my_confidence.empty': '未填',

  /* ---------------- 绑定邮箱（游客转正） ----------------
     游客身份的邮箱是合成的、密码是随机的——真实风险是清缓存/换设备就找不回
     这份报告和历史评审。文案要说的是这个真实风险，不是编一个"不绑就不给看"
     的假门槛（报告内容照常渲染在这条提示条下面）。 */
  'bind_email.title': '这份报告只存在这个浏览器里',
  'bind_email.desc': '你还没绑定邮箱——清缓存、换设备或换浏览器，这份报告和你的评审记录会永久找不回来。绑定只需要一个邮箱和密码，历史记录原样保留。',
  /* QQ 账号专用的两句。后端把 QQ 开的号也标成 is_guest=true，于是上面那两句
     "只存在这个浏览器里 / 永久找不回来"对 QQ 用户是**假的**——他随时能再用
     QQ 登回来。对用户说一句不成立的狠话，比不说更糟：下次他发现自己骗过一次，
     整条提示以后都不会再被当真。这里换成对他真实成立的好处。 */
  'bind_email_qq.title': '给账号加一个邮箱',
  'bind_email_qq.desc': '你现在用 QQ 登录。绑定邮箱之后，不依赖 QQ 也能登进来，还能收到验证与找回密码的邮件。你的历史记录原样保留，user_id 不变。',

  'bind_email.cta': '绑定邮箱',
  'bind_email_email.placeholder': '邮箱',
  'bind_email_password.placeholder': '设一个密码（至少 8 位）',
  'bind_email_submit.cta': '确认绑定',
  'bind_email.success': '绑定成功，这份报告和你的评审记录已经保住了。',
  'bind_email.error': '绑定失败',
  /* 立场三选一 = 一个控件的多个状态，走 state 变体块；理由是枚举式原因，
     走 reason 块。两者都不自造新块（契约：块名闭集，加新块要 owner 裁决）。
     叶子带 stance_/rationale_ 前缀，避免与块内其他功能的枚举撞名。 */
  'state.stance_agree': '同意',
  'state.stance_partial': '部分同意',
  'state.stance_disagree': '不同意',
  /* 理由用闭集不用自由文本：自由文本无法聚合，而这批理由的价值恰恰在于
     "你不同意评审团的时候，通常是因为什么"。 */
  'reason.rationale_own_data': '与我的实测数据不符',
  'reason.rationale_priority': '优先级判断不同',
  'reason.rationale_persona_fit': '这些人格不代表我的用户',
  'reason.rationale_evidence_weak': '证据不够充分',
  'reason.rationale_cost': '改动成本不划算',

  /* ---------------- 圆桌弃权 ---------------- */
  'abstain.label': '弃权',
  'abstain.desc': '材料里缺少这位人格评审所需的证据类型，按规矩不硬评——弃权，不计入结论。',
  'abstain.hint': '缺少：{{types}}',

  /* ---------------- 证伪信号 ----------------
     只做引擎字段的机械转述：success_criterion 在窗口内未达成 = 判断被证伪。 */
  'falsify.title': '如何证伪这份报告',
  'falsify.desc':
    '上面每条预测都写明了达成判据与验证窗口。窗口内判据未达成，即该判断被证伪——去回填「没发生」，它就不再进入同项目下一次评审的上下文。',
  'falsify.cta': '去回填验证结果',

  /* ---------------- 项目记忆 ----------------
     本次评审带入了同项目此前的历史判断。隐式注入的上下文如果不可见，
     用户会看着报告里冒出来的结论不知道从哪来的——所以带没带、带了几条、
     为什么没带，都要如实说。 */
  'project_memory.title': '本次评审带入了项目历史',
  'project_memory.desc':
    '同一项目「{{project}}」此前评审留下的 {{count}} 条判断（来自 {{reviews}} 次历史评审）已作为背景材料交给每个人格。它们是背景，不是本次材料的直接证据。',
  'project_memory.hint':
    '已被真人测试回填为「没发生」的判断不会带入——回填结果直接决定下一次评审看不看得到它。',
  'project_memory.meta': '最多带入 {{cap}} 条，按严重度优先。',
  'project_memory_none.title': '本次评审没有带入项目历史',
  /* carried=0 的四种原因，走 reason 变体块（契约允许块内叶子自由命名）。
     叶子统一带 project_memory_ 前缀：reason 是 page.report 下的公共块，
     不加前缀的话，将来别的功能往这个块里加枚举就会撞名。 */
  'reason.project_memory_anonymous_identity':
    '未登录状态不带入项目历史——匿名身份是所有访客共用的，带入会读到别人的评审结论。',
  'reason.project_memory_ledger_disabled': '本部署关闭了判断留档，因此没有历史可带。',

  /* ---------------- 预算刹车 ---------------- */
  'budget.title': '成本达到单次上限，本次少跑了环节',
  /** 两个金额都取自 report.budget，不编造任何"省了多少"。 */
  'budget.desc': '本次评审在人格环节已花费约 {{spent}}，达到单次上限 {{cap}}（budget.yaml 的 max_cost_per_run_usd）。',
  'budget_generic.desc': '本次评审达到了单次成本上限。',
  'budget.hint': '交叉质询未执行。下面没有「交叉质询」这一节，不代表人格之间没有分歧，只代表这一轮没有跑辩论。',

  /* ---------------- 评审失败 ---------------- */
  'failed.title': '本次评审失败，没有生成报告',
  'failed.desc':
    '这不是一份「没发现问题」的报告——评审没跑完，任何风险等级、共识点、立场分布都不存在。请不要据此做发布决策。',
  'failed.label': '评审对象：{{title}}',
  'failed.hint': '失败原因（后端原文）',
  'failed.empty': '后端没有回传失败原因。评审详情页的角色执行记录里可能有更具体的报错。',

  /* ---------------- 报告加载失败 ---------------- */
  'load_error.title': '报告加载失败',
  'load_error.desc': '没能把这份报告取回来，所以下面什么都不显示——这不代表评审没有结果。',

  /* ---------------- ETHICS.md 强制项：局限与注意事项 ----------------
     逐条来自 ETHICS.md（「偏见与局限性」「预筛工具，不是决策依据」
     「材料决定质量」），不新增任何该文档里没有的说法——两份材料必须能对得上。
     改这五条之前先改 ETHICS.md。 */
  'limitations.title': '局限与注意事项（Limitations & Caveats）',
  limitation_synthetic: '合成人格不是真人：立场分布反映的是 AI 人格的输出，不是任何真实用户群体的意见分布。',
  limitation_variance: '过度一致性：LLM 模拟特定群体时输出方差通常低于真实人群，真实世界里的分歧可能被低估。',
  limitation_materials:
    '材料决定质量：材料里缺少某类证据时人格会输出「未指定」，报告会标注信息缺口——「未指定」不等于「没有问题」。',
  limitation_demographic:
    'Demographic 不是因果解释：性别、年龄、地域本身不能解释偏好，不要据此把结论推广到某个真实人群。',
  limitation_feedback_loop:
    '反馈循环风险：长期用同一套人格评审迭代版本，可能让产品过度迎合模拟出来的「平均偏好」，建议定期更换人格组合。',

  /* ---------------- 交叉质询 ---------------- */
  'cross_exam.title': '交叉质询',
  'cross_exam.badge': '实际执行 {{count}} 轮',
  'cross_exam_legacy.desc':
    '这份报告由旧版本生成，交叉质询记录以旧格式保存（{{count}} 条原始条目），无法解析出争议点、反驳内容与改票明细。重新发起一次评审即可得到完整记录。',
  'cross_exam_mode_unknown.label': '未知模式',
  'cross_exam_mode_unknown.value': '未知模式（{{raw}}）',
  'cross_exam_mode_unknown.desc':
    '这份报告没有标明交叉质询的执行方式，无法判断是否真的发生过反驳——请按「未发生反驳」理解。',
  'cross_exam_fallback.desc': '本次请求的是「{{requested}}」，实际回落为「{{actual}}」。',
  'cross_exam_limitation.label': '引擎原始说明：',
  /** 整节缺席，报告也没写原因。猜一个具体理由和一声不吭同样是误导。 */
  'cross_exam_absent.desc':
    '这份报告里没有交叉质询记录。报告没有写明原因，可能是这一档评审模式不包含反驳环节，也可能是人格之间没有出现值得反驳的对立观点。请不要把它读成「大家意见一致」。',
  'cross_exam_skipped.desc':
    '本次没有执行交叉质询：人格环节的花费已达到单次成本上限，为免继续加钱而跳过（详见页面顶部的成本提示）。这不代表人格之间没有分歧，只代表这一轮没有跑辩论。',
  'cross_exam_failures.title': '交叉质询过程中的失败（{{count}} 条）',
  'cross_exam_failures.label': '未标注阶段',
  'cross_exam_failures.empty': '未给出原因',

  'dispute.empty': '未命名争议点',
  'dispute.error': '本争议点交叉质询未完成：{{reason}}',
  'dispute_empty.desc': '本次没有找到需要质询的争议点——各人格在关键判断上没有出现足够大的分歧。',
  'dispute_empty.hint': '本次没有产出可展示的争议点，原因见上方说明。',

  /**
   * 正反两方的准确叫法。引擎里 pro = 认为问题更严重的一方（A 系列），
   * con = 认为更轻的一方（B 系列）——**不是**"支持/反对某个方案"，
   * 别简写成"支持方 / 反对方"，那会把两边的意思整个说反。
   */
  'argument_pro.label': '认为问题更严重',
  'argument_con.label': '认为问题更轻',
  'argument.label': '这一方对对手论据的反驳',
  'argument.empty': '这一方没有产出反驳。',

  'change.empty': '未知人格',
  /** accepted=false 时的措辞必须是"模型声称改为"：suppressed_changes 里的
   *  to_stance 是被代码驳回的主张，不是最终立场。 */
  'change.badge': '模型声称改为 {{stance}}',
  'change.label': '置信度 {{before}} → {{after}}（变化 {{delta}}）',
  'change_threshold.label': '置信度 {{before}} → {{after}}（变化 {{delta}}，采纳阈值 θ={{threshold}}）',
  'change.error': '未采纳原因：{{reason}}',
  'change.desc': '依据（反驳原文）：{{reason}}',

  'vote.title': '改票记录',
  'vote.badge': '{{count}} 条',
  'vote_threshold.badge': '{{count}} 条 · 采纳阈值 θ={{threshold}}',
  'vote.empty': '本次未进行反驳轮，因此不存在改票记录。改票只能来自真实发生过的反驳。',
  'vote_unchanged.desc': '本轮双方立场未变。这是交叉质询中完全正常、而且常见的结果，不代表反驳没有发生。',
  'suppressed.desc': '另有 {{count}} 条立场变化由模型提出、但未被采纳（改票由代码判定，不采信模型自报）',
  'suppressed_no_update.desc':
    '另有 {{count}} 条立场变化由模型提出、但未被采纳（改票由代码判定，不采信模型自报）；本次配置为不接受立场更新',

  'confidence.title': '反驳前后的置信度',
  'confidence.unit': '{{delta}} 个百分点',

  /** calls 在引擎里按**尝试**计（失败的调用也算一次），文案必须跟着这个口径写，
   *  否则「1 次调用 / 0 tokens」看起来像个 bug。 */
  'usage.desc': '本节发起 {{calls}} 次模型调用（含失败的尝试）· 输入 {{input}} tokens · 输出 {{output}} tokens',
  'usage.hint': '（token 用量未被完整回报，实际成本可能高于账面）',
  'threshold.error': '改票阈值未能从配置读取，本次使用内置默认值（{{source}}）。',

  /* ---------------- 只读分享 ---------------- */
  'share.cta': '分享',
  'share.badge': '已公开',
  'share.title': '只读分享链接',
  'share.desc':
    '生成一条链接发给合伙人或团队，<emph>对方无需注册即可打开</emph>。任何拿到链接的人都能看，所以别发到公开场合。',
  /* 下面这两栏不是装饰，是知情同意的正文：它与后端白名单
     （share_service.to_public_dict）一一对应，改后端就要改这几条，
     否则这段说明会变成一句谎话。 */
  'share_visible.label': '对方能看到',
  'share_item_report.label': '· 报告全文（摘要、优先修复、各角色视角、共识与分歧）',
  'share_item_meta.label': '· 这次评审的标题与任务类型',
  'share_item_calibration.label': '· 评审时间与校准指标',
  'share_hidden.label': '对方看不到',
  'share_item_account.label': '· 你的账号与邮箱',
  'share_item_cost.label': '· 这次评审的花费与 token 消耗',
  'share_item_material.label': '· 你上传的原始材料',
  'share.aria': '分享链接',
  'share_create.cta': '生成分享链接',
  'share_revoke.cta': '撤销',
  'share.hint': '撤销后这条链接立刻失效，已经打开过的人也无法再次访问。再次分享会生成一条新链接。',
  'share.error': '生成分享链接失败',
  'share_revoke.error': '撤销失败',
  /** 剪贴板 API 在非 HTTPS / 无权限时会拒绝。不弹「复制成功」的假消息。 */
  'share_copy.error': '浏览器拒绝了剪贴板访问，请手动选中上面的链接复制',

  /* ---------------- HTML 可视化版本 ---------------- */
  'html.cta': 'HTML 可视化报告',
  'html.aria': 'HTML 报告',
  'html.tooltip': 'HTML 版本还在生成中',
  'html.empty': '后端没有回传这份报告的 HTML 版本（也没有说明原因）。',
  'html.error': '取 HTML 版本失败：{{reason}}',
  'html.desc': '这份报告没有 HTML 可视化版本：{{reason}}上面的网页内容和 JSON / Markdown 导出不受影响。',

  /* ---------------- 执行摘要 ---------------- */
  'summary.title': '发布风险评估：{{risk}}',
  /** 缺等级要说是「报告没给」，不是「评估结果是中风险」。两种缺法分两条 key。 */
  'summary_risk_missing.desc': '这份报告没有给出发布风险等级（收到的取值「{{raw}}」不在已知档位里），这里不替它推断。',
  'summary_risk_absent.desc': '这份报告没有给出发布风险等级（执行摘要里没有 release_risk），这里不替它推断。',
  'summary_stance.label': '评审团主流立场',
  'summary_evidence.label': '证据充分度',
  /** 口径跟 aggregator.compute_consensus 的 docstring 对齐：
   *  questioned_points 是"只有个别人格提出的关切"，写成「存疑点」会被读反。 */
  'summary_consensus.label': '共识议题 / 个别人格单独提出',
  'summary_consensus.hint': '判定口径：同一议题被 ≥{{min}}/{{total}} 位人格各自独立提出',

  /* ---------------- 立场分布 ---------------- */
  'stance.title': '立场分布（{{count}} 个人格）',
  'stance.empty': '暂无人格立场数据',
  /** persona_note 既没有 stance 也没有 primary_stance 时的分组名。
   *  它是前端造的分组，不是引擎的立场枚举——立场枚举是 wire key，永不翻译。 */
  'stance.value': '未表态',

  /* ---------------- 校准指标 ---------------- */
  'calibration.title': '校准指标',
  'calibration.success': '校准通过',
  'calibration.error': '校准未达标——结论请谨慎采信',
  'calibration.empty': '本次评审未运行校准检查',

  /* ---------------- 优先修复项 ---------------- */
  'fixes.title': '优先修复项',
  /** dedup_method === 'lexical' 时的如实标注。semantic 正常态不提示。 */
  'fixes.hint': '（本次按词面相似度聚类——语义模型未安装，措辞略异的同一问题可能被拆成两条）',
  'fix_why.label': '为什么重要',
  'fix_suggestion.label': '修复建议',
  'fix_personas.label': '提出的人格',

  /* ---------------- 人格视角 ---------------- */
  'personas.title': '人格视角',
  'persona_issues.label': '关键议题',
  'persona_evidence.label': '关键证据',

  /* ---------------- 议题共识明细 ---------------- */
  'consensus.title': '议题共识明细',
  'consensus.hint': '共识 = 同一议题被 ≥{{min}}/{{total}} 位人格各自独立提出',
  'consensus.badge': '共识',
  'consensus_single.badge': '个别提出',
  'consensus.meta': '{{count}} 人提出',
  /** persona_count 与 personas 都没给：如实说不知道，不写 0（0 会被读成"没人提"）。 */
  'consensus_unknown.meta': '提出人数未记录',
  'consensus.desc': '合并的措辞：{{variants}}',

  /* ---------------- 主要分歧 ---------------- */
  /* ---------------- 议题 × 人格立场矩阵 ----------------
     这一块是本轮新加的，整块文案原先硬编码在 tsx 里（标题、表头、两条
     title 提示、图例），英文界面上会直接漏出中文。aria 那条有两个计数，
     按契约 §3.4 例 4 的口径：复数只挂一个（议题数），人格数当普通插值。 */
  /** 打印弹窗被浏览器拦下时的提示。此前这里是 `if (!win) return`——
   *  点 PDF 什么都不发生、也没有任何报错，用户只会以为按钮坏了。 */
  'print_blocked.error': '浏览器拦下了打印窗口。请允许本站弹出窗口后再点一次 PDF；也可以先点 HTML 下载报告，再用浏览器打开并打印。',

  'matrix.title': '议题 × 人格立场矩阵',
  'matrix.aria': '议题人格立场矩阵：{{count}} 个议题 × {{personas}} 个人格',
  'matrix_topic.label': '议题',
  /** 后端没给 topic 时的占位。**不是**"无分歧"——是这条分歧没带标题。 */
  'matrix_topic.empty': '未命名议题',
  /** 格子的 title 提示。{{stance}} 是后端立场枚举原文（wire 值，永不翻译）。 */
  'matrix_cell.tooltip': '{{persona}}：{{stance}}',
  'matrix_cell_unmentioned.tooltip': '{{persona}}：未提及',
  'matrix_unmentioned.label': '未提及',

  'disagreements.title': '主要分歧',
  'disagreement.hint': '建议：{{text}}',

  /* ---------------- 信息缺口 / 下一步 ---------------- */
  'gaps.title': '信息缺口',
  'next_test.title': '建议的下一步真人验证',
  'next_test_tasks.label': '验证任务',
  /** 标题不能写「建议招募的人群」：recruit_types 是本次 AI 面板覆盖的受众特征串
   *  （取自人格档案的真实属性），引擎并没有算"你该找谁"。写成招募建议
   *  就是把没算过的东西说成算过了——用户会照着去招募真人。 */
  'next_test_audience.label': '本次面板覆盖的受众特征',
  'next_test_materials.label': '需要补充的材料',

  /* ---------------- 伦理合规 ---------------- */
  'compliance.title': '人格伦理合规',
  'compliance.badge': '{{status}} · {{score}} 分',

  /* ---------------- 评估评分卡 ---------------- */
  'evaluation.title': '评估评分卡',
  'evaluation_critical.title': '关键失败项',
  /** 标出满分：右边那块维度分是 0–3，不写清楚两个数看起来是同一把尺子。 */
  'evaluation_overall.label': '总体评分（满分 100）',
  'evaluation.meta': '{{passed}}/{{total}} 维度通过',
  'evaluation_dimension.label': '维度评分（每项满分 3，合格线 2）',
  'evaluation_dimension.empty': '本地词表里没有这个维度的说明',
  /** 维度 id 不在本地词表里时明说不认识，不把 snake_case 当正常标题直出。 */
  'evaluation_dimension.value': '{{id}}（未知维度）',
  'evaluation.cta': '运行评估',
  'evaluation_full.cta': '查看完整评估',
  /** tApiError 的 fallbackKey（无插值）。 */
  'evaluation.error': '运行质量评估失败',
  'evaluation_run.error': '运行评估失败：{{reason}}',

  /* ---------------- 伦理报告 ---------------- */
  'ethics.title': '伦理报告',
  'ethics_score.label': '伦理评分',
  'ethics_stereotype.label': '刻板印象风险',
  'ethics_violations.label': '违规项 {{count}}',

  /* ---------------- 价值回填 ---------------- */
  'feedback.title': '这份报告真的有用吗？',
  'feedback.desc': '反馈将用于衡量建议采纳与决策影响，不用调用次数冒充价值。',
  'feedback_useful.cta': '有用',
  'feedback_useless.cta': '没帮助',
  'feedback_adopted.label': '实际准备采纳哪些建议？',
  'feedback_fix.value': '建议 {{index}}',
  'feedback_hours.label': '预计节省工时',
  'feedback_pay.label': '愿意为本次支付（USD）',
  'feedback_decision.label': '报告改变了我的产品或发布决策',
  'feedback.cta': '提交反馈',
  'feedback.error': '反馈提交失败',
  /** {{section}} 传 t('nav.item.ledger')：导航项改名时这句自动跟着改，
   *  不会出现"页面让我去某某页、导航里根本没这一项"。 */
  'feedback.success': '已记录。后续可在「{{section}}」查看价值指标。',

  /* ---------------- 匿名体验版 ---------------- */
  'gated.subtitle': '体验版报告',
  'gated_summary.title': '执行摘要',
  'gated_risk.label': '发布风险',
  'gated_recommendation.label': '主要建议',
  'gated_fix.title': '优先修复项（预览）',
  'gated.hint': '还有 {{count}} 条优先修复项、{{notes}} 条角色视角未展示',
  /** 这句话必须和代码对得上：认领靠的是这台浏览器本地记下的 id，
   *  所以「在这台设备上」不是废话，是这句承诺真实的边界。 */
  'gated.desc': '在这台设备上登录或注册后，这份报告会自动归到你的账号名下，完整内容和历史记录都能在「评审历史」里打开。',
  'gated.cta': '登录 / 注册看完整报告',

  /* ---------------- Markdown 导出件 ----------------
     它不在 JSX 里，按"渲染到界面"的口径扫描会整批漏掉，但它是用户真会发给
     别人的文件。网页上置顶的坏消息（谁被校验拦下、有没有因预算跳过环节、
     交叉质询是三档里的哪一种）在导出件里必须一条不少。 */
  'md_banner.desc': '本报告不得作为「玩家调研结果」「用户调查数据」「真实玩家意见分布」对外展示或引用。',
  /** 契约 8.4：导出的是文件，脱离界面之后没人知道它是什么语言。 */
  'md_lang.value': '本报告正文语言：{{lang}}',
  /** report_json.meta 里没有 language：如实说「未记录」，**不许当成中文**（契约 D7）。 */
  'md_lang.empty': '本报告正文语言：未记录（生成这份报告时还没有记录产出语言）',
  'md_lang_zh.value': '中文',
  'md_lang_en.value': '英文',
  'md_gate.title': '有 {{count}} 位人格的输出没通过质量校验，未计入以下结论：',
  'md_budget.hint': '交叉质询未执行——本报告没有这一节，不代表人格之间没有分歧。',
  'md_risk.title': '发布风险：{{risk}}',
  'md_risk.empty': '未知',
  'md_stance.label': '主流立场：{{value}}',
  'md_evidence.label': '证据充分度：{{value}}',
  'md_fix.label': '建议',
  'md_cross_exam_legacy.desc': '这份报告由旧版本生成，交叉质询记录格式过旧，无法解析出反驳与改票明细。',
  'md_cross_exam.label': '执行方式：{{mode}}',
  'md_cross_exam.empty': '无法判断是否真的发生过反驳。',
  'md_cross_exam.hint': '引擎说明：{{text}}',
  'md_vote.label': '改票记录：{{count}} 条',
  'md_vote_none.label': '改票记录：{{count}} 条（本轮双方立场未变，属正常结果）',
  'md_vote.empty': '改票记录：不适用（未进行反驳轮）',
  'md_failures.label': '过程中有 {{count}} 条失败：{{list}}',
  'md_cross_exam_skipped.desc':
    '本次没有执行交叉质询：成本已达单次上限，为免继续加钱而跳过。这不代表人格之间没有分歧。',
  'md_cross_exam_absent.desc':
    '这份报告里没有交叉质询记录，报告也没有写明原因（可能是这一档评审模式不包含反驳环节，也可能是没有出现值得反驳的对立观点）。请不要读成「大家意见一致」。',
} satisfies Messages
