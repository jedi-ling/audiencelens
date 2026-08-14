// owner: agent-9。访客不一定是作者 —— 措辞规矩见 zh/page.shared.ts 的文件头。
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Shared report',

  'revoked.title': 'This link no longer works',
  'revoked.desc':
    'This share link doesn’t exist, or its author has revoked it. Ask whoever sent it to you for a new one.',
  // 访客可能第一次听说这个产品，所以是一句提问式入口，不是"回到首页"。
  'revoked.cta': 'What is AudienceLens?',

  'load_error.title': 'Couldn’t load the report',
  'load_error.desc': 'The report didn’t come back from the server.',

  'header.title': 'Review report',
  'header.meta_one': '{{count}} persona took part',
  'header.meta_other': '{{count}} personas took part',
  'share_note.badge': 'Read-only report, shared by its author',

  'summary.title': 'Overall verdict',
  'release_risk.label': 'Release risk: <v>{{value}}</v>',
  'evidence_quality.label': 'Evidence quality: <v>{{value}}</v>',

  'fixes.title_one': 'Priority fix ({{count}})',
  'fixes.title_other': 'Priority fixes ({{count}})',
  'suggestion.label': 'Suggested fix: {{text}}',

  'agreed.title': 'Where most agreed',
  'questioned.title': 'Where doubts came up',
  'notes.title_one': 'What the persona said ({{count}})',
  'notes.title_other': 'What each persona said ({{count}})',
  'gaps.title': 'Information gaps',

  'footer.desc': 'This report was produced by a panel of AudienceLens AI personas.',
  'footer.cta': 'Run a panel on your own work',
} satisfies Messages
