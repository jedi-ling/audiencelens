// owner: agent-11。见 zh/error.fetch.ts 的文件头（与 error.api.* 的分工写在那里）。
import type { Messages } from '@/i18n/types'

export default {
  review_list: 'Could not load your reviews',
  review: 'Could not load this review',
  report: 'Could not load this report',
  personas: 'Could not load the personas',
  persona_packs: 'Could not load the persona packs',
  examples: 'Could not load the examples',
  extract_materials: 'Could not read that file',
  delete_review: 'Could not delete this review',
  task_types: 'Could not load the task types',
  review_modes: 'Could not load the review modes',
  review_result: 'Could not load the review result',
  skills: 'Could not load the skills',
  run_evaluation: 'Could not run the quality evaluation',
  evaluation: 'Could not load the quality evaluation',
  ethics: 'Could not load the ethics check',

  http_status: '{{message}} (HTTP {{status}})',

  separator: '; ',
} satisfies Messages
