// owner: batch-0。通用动作词，页面 agent 只读。
import type { Messages } from '@/i18n/types'

export default {
  submit: '提交',
  cancel: '取消',
  confirm: '确定',
  save: '保存',
  edit: '编辑',
  delete: '删除',
  retry: '重试',
  back: '返回',
  next: '下一步',
  prev: '上一步',
  close: '关闭',
  copy: '复制',
  refresh: '刷新',
  load_more: '加载更多',
  download: '下载',
  share: '分享',
  upload: '上传',
  remove: '移除',
  clear: '清空',
  expand: '展开',
  collapse: '收起',
  view_details: '查看详情',

  /**
   * 删号二次确认短语。
   *
   * **这条是全仓唯一一条 zh 与 en 必须字面相同的 key**，i18n:check 对它单列豁免。
   *
   * 原因：它不是文案，是凭据。后端 platform.py 的 DELETE_CONFIRM_PHRASE
   * 做的是中文字面量相等比较，翻译了英文用户就永远删不掉账号，而且报错还是中文。
   * 提示语（"请原样输入下面这句中文"）可以翻，要用户敲进去的**这一句不能翻**。
   * 见契约 6.8。
   */
  delete_account_phrase: '删除我的账号',
} satisfies Messages
