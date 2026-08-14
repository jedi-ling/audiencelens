/**
 * Task types page (TaskTypesPage.tsx). owner: agent 7.
 *
 * ⚠ 清单本身（name_zh / description / stance_enum / …）不在这里，
 * 英文事实源是后端 catalog.en-US.json，见 zh/page.task_types.ts 的文件头。
 *
 * modal_name.label 刻意译成 "Chinese name"：那个字段的值就是中文的 name_zh，
 * 译成 "Name" 会让英文用户以为系统只是没翻译好。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Task types',
  'header.title': 'Task types',
  'count.total_one': '{{count}} review task type',
  'count.total_other': '{{count}} review task types',
  'header.loading': 'Loading the task type list',
  'header.error': 'Could not load the task type list',

  // ---- List failed to load ----
  'list.error': 'Failed to load task types',
  'list_error.title': 'Task types unavailable',
  'list_error.desc':
    '{{reason}} — this does not mean there are no task types; the list itself could not be fetched. Please try again.',
  'list_error.cta': 'Reload',
  'list.empty': 'The backend is not offering any review task types right now',

  // ---- Category filter ----
  'filter.tab': 'All',
  'category_development.label': 'Development',
  'category_operations.label': 'Launch and live ops',
  'category_community.label': 'Community',
  'category_product.label': 'General product',
  'category_other.label': 'Other',

  // ---- Cards ----
  'card_stance.label': 'Stances:',
  'card_score.label': 'Score dimensions:',
  'card.cta': 'View details →',

  // ---- Detail dialog ----
  'modal.title': 'Task type detail',
  'modal_id.label': 'ID',
  'modal_name.label': 'Chinese name (name_zh)',
  'modal_desc.label': 'Description',
  'modal_stance.label': 'Stance enum (stance_enum)',
  'modal_score.label': 'Score dimensions (score_dimensions)',
  'modal_base.label': 'Base dimensions (base_dimensions)',
  'detail.error': 'Failed to load the task type detail',
  'detail_error.title': 'Could not load the detail',
  'detail_error.hint': 'Please try again in a moment',
} satisfies Messages
