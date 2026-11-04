/**
 * 样例报告页（/samples）。只读，不需要登录或 API Key。
 *
 * 文案要点：如实说明这些是**真实引擎运行的原始产物、没有手工修改**，也是合成评审，
 * 不是真实用户研究；没通过校验的人格和没跑成的交叉质询照样展示。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '样例报告',
  'header.title': '样例报告',
  'header.desc':
    '下面几份报告由 AudienceLens 引擎对虚构的产品材料真实运行生成，原样保存，没有手工修改。点开可以看到完整的 HTML 报告。',
  'notice.desc':
    '这些都是 AI 合成评审，不是真实用户研究。没通过校验的人格不计入结论，报告顶部会如实标出。',
  'load.pending': '正在加载样例列表…',
  'load.error': '样例列表没能加载出来，请稍后刷新重试。',
  'open.cta': '打开报告',
  'model.label': '模型',
  'date.label': '生成日期',
  'cost.label': '本次花费',
  'personas.label': '通过校验的人格',
  'disputes.label': '交叉质询：{{count}} 个争议点，每个都跑了一轮反驳',
  'no_cross_exam.hint': '这份报告里人格之间没有足够明显的分歧，交叉质询这一步没有运行。',
} satisfies Messages
