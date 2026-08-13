// owner: batch-0。页面 agent 只读，不要往这里加页面专属文案。
// 判断标准（契约 11 的判断树）：只有"任何页面都可能原样用得上"的通用界面词
// 才进这里。有具体语义的（"正在解析材料…"）进 page.*，用角色段 pending。
import type { Messages } from '@/i18n/types'

export default {
  // ---- 通用加载态。页面不要自己写"加载中"，写了就会出现 5 种省略号写法 ----
  loading: '加载中…',
  submitting: '提交中…',
  saving: '保存中…',
  sending: '发送中…',
  deleting: '删除中…',
  processing: '处理中…',

  // ---- 通用结果态 ----
  // 空状态**必须有文案**：禁止渲染空白 div，用户分不清"没有数据"和"加载失败"。
  empty: '暂无数据',
  error: '出错了',
  // tApiError 的 fallbackKey 默认用它。刻意不写"未知错误，请重试"——
  // 我们并不知道重试有没有用，写了就是在给一个没有依据的建议。
  unknown_error: '操作失败',
  success: '操作成功',
  copied: '已复制',
  copy_failed: '复制失败',

  // ---- 通用标记 ----
  required_mark: '必填',
  optional_mark: '选填',
  // report_lang === null 时用它。**不许当成 zh-CN**——null 分支和 'zh-CN'
  // 分支是两个分支，见契约 D7。
  not_recorded: '未记录',

  // ---- 语言切换器 ----
  language: '语言',
  language_aria: '切换界面语言',
  // 只切界面，不切已生成报告的正文——正文语言在评审入队瞬间就冻结了。
  // 这句必须说出来，否则用户切成英文后打开旧报告会以为系统坏了。
  language_hint: '只影响界面语言，不影响已生成报告的正文',
} satisfies Messages
