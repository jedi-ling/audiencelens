/**
 * owner: agent-catalog-frontend。见 zh/catalog.eval_dimension.ts 的文件头。
 *
 * 译法口径：
 *   1. label 是维度卡片的标题，两三个词、句首大写，不写成一句话。
 *   2. desc 保留中文侧的"是否…而不是…"结构。这个对照句式是这批文案的实质内容——
 *      每一条都在说"什么算达标、什么是看起来像达标的东西"，砍掉后半句会让维度
 *      退化成一个谁都会说好的空标准。
 *   3. 不引入后端没有的判分口径（mock-data.ts 的注释对中文侧立过这条），
 *      所以这里只译，不补充"怎么算高分"之类中文侧没有的话。
 */
import type { Messages } from '@/i18n/types'

export default {
  'persona_differentiation.label': 'Persona differentiation',
  'persona_differentiation.desc':
    'Whether each persona holds a stable point of view backed by its behavior rules, not just different wording',

  'input_grounding.label': 'Grounding in your material',
  'input_grounding.desc':
    'Whether the findings keep citing details from the material you submitted, instead of returning generic advice',

  'actionability.label': 'Actionability',
  'actionability.desc':
    'Whether the P0/P1/P2 actions are specific and prioritized, instead of stated in general terms',

  'segment_conflict.label': 'Segment conflict',
  'segment_conflict.desc':
    'Whether real disagreement showed up between segments — the kind that changes a product decision',

  'risk_detection.label': 'Risk detection',
  'risk_detection.desc':
    'Whether it names concrete blockers, the reasons people object, and the risks per segment',

  'ethical_persona_use.label': 'Ethical persona use',
  'ethical_persona_use.desc':
    'Whether it avoids stereotyping and treats demographics and MBTI-style fields as weak modifiers only',

  'report_structure.label': 'Report structure',
  'report_structure.desc': 'Whether the report has every required section and every section has real content',

  'calibration_honesty.label': 'Honesty of conclusions',
  'calibration_honesty.desc':
    'Whether findings are stated as hypotheses to be tested, with a real way to test them, instead of predicting success',
} satisfies Messages
