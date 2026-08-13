/**
 * 浏览器标题模板与 meta description。owner: batch-0。
 *
 * 页面自己的标题写在 page.<x>.meta.title，由 useDocumentTitle 套进这里的模板。
 * 品牌名不翻译，两侧模板同形。
 */
import type { Messages } from '@/i18n/types'

export default {
  title_template: '{{page}} · AudienceLens',
  // index.html 里那条静态中文 description 的运行时版本。
  // ⚠ 这不是 SEO——纯客户端渲染，爬虫读不到运行时改写的 meta，见 head.ts 文件头。
  description: '多代理合成用户评审系统：用一组有身份、有偏好的合成受众评审你的游戏概念、Demo 与商店页，给出可执行的分歧与共识。',
} satisfies Messages
