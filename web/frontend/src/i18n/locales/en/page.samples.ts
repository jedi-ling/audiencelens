import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Sample reports',
  'header.title': 'Sample reports',
  'header.desc':
    'Each report below was produced by a real AudienceLens engine run on fictional product material and the model output is unedited (only the stylesheet of the HTML report was updated after a CSS fix). Open one to see the full HTML report.',
  'notice.desc':
    'These are AI-generated synthetic reviews, not real user research. Personas that failed validation are left out of the conclusions, and the report says so at the top.',
  'load.pending': 'Loading the sample list…',
  'load.error': "The sample list didn't load. Refresh the page to try again.",
  'open.cta': 'Open report',
  'model.label': 'Model',
  'date.label': 'Generated',
  'cost.label': 'Run cost',
  'personas.label': 'Personas passing validation',
  'disputes.label_one': 'Cross-examination: {{count}} dispute, one rebuttal round',
  'disputes.label_other': 'Cross-examination: {{count}} disputes, one rebuttal round each',
  'no_cross_exam.hint': 'The personas in this report did not disagree enough for the cross-examination step to run.',
} satisfies Messages
