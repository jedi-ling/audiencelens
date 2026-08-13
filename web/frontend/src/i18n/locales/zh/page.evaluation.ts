/**
 * 评估报告页（EvaluationPage.tsx）。owner: agent 6。
 *
 * 这一页上同时存在**两个量纲**，文案必须把它们区分开，否则用户看到的是自相矛盾的一页：
 *   · scorecard.overall_score 是 0–100（所以有 overall.hint「满分 100」）
 *   · 单维度分是 0–3，合格线 2（所以 score.label 里写死了合格线）
 * 这两句提示不是可选的补充说明，是这一页能被读懂的前提。
 *
 * 不在本表内的中文（不是漏了，是不归本页）：
 *   · EVALUATION_DIMENSIONS 的 name / description —— 前端目录，overlay 归 batch-0
 *   · ETHICS_SEVERITY_LABELS / stereotypeRiskLabel —— enum 域，归 batch-0
 *   · SKILLS[].name、scorecard.critical_failures[]、result.details、violation.detail
 *     —— 后端产出的自由文本
 * 逐条见交付报告。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '评估报告',

  'header.title': '评估报告',
  'header.loading': '加载评估报告...',
  'header.aria': '返回评审报告',
  'back.cta': '返回评审报告',

  // 「还没生成」和「加载失败」必须是两条不同的话：前者是正常状态，后者是故障。
  // 混成一句会让用户对着一个 500 反复点"重新运行评估"。
  'not_generated.title': '评估报告尚未生成',
  'not_generated.desc': '请先在评审报告页运行评估',
  'load_error.title': '没能加载评估报告',
  'load_error.desc': '{{message}}——这不代表评估没跑过，接口可能只是临时抖动',

  // ---- 总体评分 ----
  'overall.title': '总体评分',
  'overall.desc': '{{passed}}/{{count}} 维度通过',
  'overall.hint': '满分 100',
  // 通过/未通过的四条状态文案。总体那两条带图标、语气更重，
  // 与维度徽标的「通过 / 未通过」刻意不同措辞，不要合并。
  'state.overall_pass': '✅ 评估通过',
  'state.overall_fail': '❌ 评估未通过',
  'state.pass': '通过',
  'state.fail': '未通过',

  'radar.title': '维度雷达图',
  // recharts 的 series 名，会出现在 tooltip 里。
  'radar.label': '评分',

  'critical.title': '关键失败项',

  // ---- 维度详情 ----
  'dimensions.title': '维度详情',
  // 维度 id 在本地词表里找不到时用它。**不能把 snake_case 原样当标题直出**——
  // 那看起来像是产品本来就长这样，没人会去查为什么。
  'unknown_dimension.label': '{{id}}（未知维度）',
  'dimension.hint': '本地词表里没有这个维度的说明',
  // 合格线 2 分是后端定的（evaluation_service 里 passed = score >= 2）。
  // 写进文案是刻意的：不写的话 0–3 这个量纲在界面上没有任何解释。
  'score.label': '评分（合格线 2 分）',
  'score.value': '{{score}}/{{max}}',

  // ---- 伦理摘要 ----
  // 别写死"8 维"：维度条数来自 scorecard.results，后端 rubric 改了这句就成假话。
  'ethics_error.desc':
    '伦理摘要没能加载（{{message}}）——不代表没有伦理问题，只是这一块没取到。上面的 {{count}} 项维度评分不受影响。',
  'ethics.title': '伦理摘要',
  'ethics_score.label': '伦理评分',
  'stereotype.label': '刻板印象风险',
  'violations.label': '违规项 {{count}}',

  // ---- 时间线 ----
  'timeline.title': '评估时间线',
  'created.label': '评审创建',
  'completed.label': '评审完成',
  'skill.label': '使用技能',

  // created_at / completed_at 取不到时显示它。取不到就明说取不到——
  // 以前 new Date(null) → 1970-01-01，页面上煞有介事地显示一个假时间。
  // zh/en 字面相同：它是"没有这个值"的符号，不是句子。
  'time.empty': '—',
} satisfies Messages
