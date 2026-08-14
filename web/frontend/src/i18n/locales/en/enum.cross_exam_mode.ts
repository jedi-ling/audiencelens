// owner: agent-1（见 zh/enum.cross_exam_mode.ts 的文件头）
import type { Messages } from '@/i18n/types'

export default {
  'derived_summary.label': 'Derived summary (no rebuttal round)',
  'moderated_rebuttal.label': 'Moderated rebuttal (1 round)',
  'multi_agent_rebuttal.label': 'Multi-agent rebuttal',

  'derived_summary.desc':
    'No rebuttal round ran here. Everything in this section is derived from what each persona wrote during its own independent review — no persona argued against another, and nobody changed their vote as a result.',
  // "in a single pass" 是这一档与下一档的**唯一**区别，不能省。
  'moderated_rebuttal.desc':
    'One moderated rebuttal round ran: a single model call was given both sides’ recorded arguments and produced the rebuttals and the updated stances in a single pass. This is not each persona speaking again on its own.',
  'multi_agent_rebuttal.desc':
    'A multi-agent rebuttal ran: every persona involved was called again with the opposing arguments in hand, and each produced its own rebuttal and final stance.',
} satisfies Messages
