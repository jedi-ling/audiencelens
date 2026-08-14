/**
 * store 层拉取失败时的兜底文案。owner: batch-0。
 *
 * 这批文案替换的是 store 里 `e instanceof Error ? e.message : '中文兜底'` 的后半段，
 * 前半段（把 e.message 原样甩给用户）也一并交给 tApiError 处理——
 * 那个写法会在网络层抛 TypeError 时把 "Failed to fetch" 直接显示在界面上。
 *
 * ⚠ **已知限制，别当成没有**：store 存的是**已翻好的字符串**，捕获那一刻定型。
 * 用户在错误横幅还挂着的时候切语言，那条横幅不会跟着变。
 * 正确的终局形态是 store 只存 code/error 对象、由页面在渲染时翻译，
 * 但那要改 store 的公开形状（error: string | null），会波及 batch-1 的页面文件。
 * 本期不做，记在交付报告里。
 */
import type { Messages } from '@/i18n/types'

export default {
  /** session-store.bootstrap：连不上后端，整个应用起不来的那一种。 */
  bootstrap: '后端连接失败',
  review_list: '评审列表加载失败',
  examples: '示例加载失败',
  personas: '角色列表加载失败',
} satisfies Messages
