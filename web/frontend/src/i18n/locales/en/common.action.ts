// owner: batch-0
import type { Messages } from '@/i18n/types'

export default {
  submit: 'Submit',
  cancel: 'Cancel',
  confirm: 'Confirm',
  save: 'Save',
  edit: 'Edit',
  delete: 'Delete',
  retry: 'Try again',
  back: 'Back',
  next: 'Next',
  prev: 'Back',
  close: 'Close',
  copy: 'Copy',
  refresh: 'Refresh',
  load_more: 'Load more',
  download: 'Download',
  share: 'Share',
  upload: 'Upload',
  remove: 'Remove',
  clear: 'Clear',
  expand: 'Expand',
  collapse: 'Collapse',
  view_details: 'View details',

  // 刻意与 zh 侧字面相同 —— 见 zh/common.action.ts 里那段注释。
  // 这是后端的字面量比较凭据，翻译它 = 英文用户永远删不掉账号。
  // i18n:check 的"en 不许与 zh 相同"断言对这一条单列豁免。
  delete_account_phrase: '删除我的账号',
} satisfies Messages
