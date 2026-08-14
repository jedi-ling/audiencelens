// owner: agent-10（与 zh/page.history.ts 同一个 owner）。
// 复数：带 count 的 key 在 en 侧必须同时有 _one 和 _other，调用方永远只写逻辑 key。
// count.total_and_loaded 的复数挂在总数（count）上，已显示数是普通插值——
// 一句话里两个计数时只能挂一个，见 zh 侧文件头。
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': 'Review history',
  'header.title': 'Review history',
  'header.desc': 'Every review you have started — open one to read the report or pick it back up',

  'count.loaded_only_one': '{{count}} shown',
  'count.loaded_only_other': '{{count}} shown',
  'count.total_and_loaded_one': '{{count}} review · {{loaded}} shown',
  'count.total_and_loaded_other': '{{count}} reviews · {{loaded}} shown',
  'count.total_one': '{{count}} review',
  'count.total_other': '{{count}} reviews',

  // 状态徽章搬去 enum.review_status.* 了，见 zh 侧注释。

  // 模式徽章读 enum.mode_badge.*，见 zh 侧注释。

  'list_empty.title': 'No reviews yet',
  'list_empty.cta': 'Run your first review →',
  'load_error.title': 'Could not load your review history',
  'load_error.desc': 'Nothing has been deleted — try again, or come back in a moment',

  'load.error': 'Could not load your reviews',
  'load_more.error': 'Could not load any more reviews',
  'delete.error': 'Could not delete that review',

  'load_more.cta': 'Load more',
  // 分隔符在值里（见 zh 侧注释）。
  'load_more.remaining_one': '· {{count}} left',
  'load_more.remaining_other': '· {{count}} left',
  'load_more.success_one': 'All {{count}} review loaded',
  'load_more.success_other': 'All {{count}} reviews loaded',

  // 中文用「」，英文侧一律换成 “…”（U+201C/201D），不留中文书名号（契约 6.9）。
  'confirm_dialog.aria': 'Confirm deleting “{{title}}”',
  'confirm_dialog.desc':
    'Delete “<name>{{title}}</name>”?<br/><note>The report, every persona’s take and the entire follow-up thread go with it. This cannot be undone.</note>',
  'item.aria': 'Delete “{{title}}”',
  'item.tooltip': 'Delete this review (you will be asked to confirm)',

  'group.meta_one': 'Ongoing project · {{count}} review',
  'group.meta_other': 'Ongoing project · {{count}} reviews',
} satisfies Messages
