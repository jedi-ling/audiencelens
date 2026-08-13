/**
 * <title> 与 <meta name="description"> 的 ui_lang 同步。
 *
 * ⚠ **这不是 SEO 方案。** 本站是纯客户端渲染（Vite + BrowserRouter），
 * 爬虫拿到的是 index.html 那一份静态 HTML，运行时改写的 meta 它读不到。
 * 这里做的只有一件事：分享链接预览 / 浏览器标签页 / 收藏夹里不要显示错的语言。
 * 不要因为加了这一层就以为 SEO 有了——真要 SEO 得上 SSR 或预渲染，那是另一件事。
 *
 * 现状（契约 6.3 / 6.4）：全站 document.title 零引用，任何路由下标题都是
 * index.html 里那一串中文；index.html 里根本没有 meta description。
 */

import { useEffect } from 'react'
import { t } from './runtime'
import { useLocale } from './locale'
import type { PlainMessageKey } from './keys.gen'

/** 只接受无插值的 key，所以这里可以安全地少传一个实参。 */
const tPlain = t as unknown as (key: PlainMessageKey) => string

/**
 * 每个路由页面**必须**在顶层调用一次。这是交付项，不是可选。
 *
 * 传的是 key 不是已翻好的字符串——传字符串的话，调用方得自己 useLocale()
 * 才能在切语言时更新，而那一步一定有人忘写，表现是「切了语言，标签页标题没变」。
 */
export function useDocumentTitle(pageTitleKey: PlainMessageKey): void {
  const locale = useLocale()
  useEffect(() => {
    document.title = t('common.meta.title_template', { page: tPlain(pageTitleKey) })
  }, [pageTitleKey, locale])
}

/** 覆盖 index.html 里的静态中文 description。没有这个标签就什么也不做。 */
export function setMetaDescription(text: string): void {
  const el = document.querySelector('meta[name="description"]')
  if (!el) {
    console.error('[i18n/head] index.html 缺 <meta name="description">，描述未更新')
    return
  }
  el.setAttribute('content', text)
}
