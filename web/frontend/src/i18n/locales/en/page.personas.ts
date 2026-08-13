/**
 * Persona library page. owner: agent-8 (same owner as zh/page.personas.ts).
 *
 * 译注：人格本身的字段不在这张表里（契约 10.3，人格身份不本地化），
 * 角色包名与分类名属目录数据、owner 是 batch-0（契约 D5）。
 * 这里只有页面框架文案。
 *
 * "试试清除搜索词或选择「全部」" 里的「全部」指的是上面那颗 filter_all 按钮，
 * 所以英文用的引号里必须是 filter_all 的英文值 "All"，两条改一条就得一起改。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Persona library',
  'header.title': 'Persona library',

  'filter.title': 'Filter by pack',
  filter_all: 'All',
  'filter.cta': 'Filters',
  'search.placeholder': 'Search personas…',
  pack_unknown: 'Unknown',

  compare_enter: 'Compare mode',
  compare_exit: 'Exit compare',
  'compare.title': 'Persona comparison',
  'compare.label': 'Compare',

  'rules.title': 'Decision rules',
  'triggers.title': 'Triggers',

  'list.pending': 'Loading personas…',
  'list_empty.title': 'No personas match',
  'list_empty.desc': 'Try clearing the search, or pick “All”.',
  'list_empty.cta': 'Clear search',
} satisfies Messages
