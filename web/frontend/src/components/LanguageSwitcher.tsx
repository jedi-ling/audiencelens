import { useEffect, useRef, useState } from 'react'
import { Globe, Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { LOCALES, LOCALE_ENDONYM, getLocale, setLocale, useLocale, type Locale } from '@/i18n/locale'
import { t } from '@/i18n/runtime'

/**
 * ui_lang 切换器。owner: batch-0。
 *
 * 三件事是刻意的，改之前先读：
 *
 * 1. **只有一种语言时整个组件返回 null。** 默认构建（VITE_AL_LOCALES=zh）下
 *    顶栏一个像素都不多占——顶部导航已经有 10 项 + 主按钮 + 账户区，
 *    塞一个只有一个选项的下拉是纯噪声。开了 zh,en 才出现。
 *
 * 2. **选项用语言自称显示**（中文 / English），不翻译。见 locale.ts 的
 *    LOCALE_ENDONYM 注释。
 *
 * 3. **切换失败就是失败，不静默停在旧语言。** setLocale 会 await 语料分包，
 *    分包 404（发版后旧 chunk）会抛。这里把错误显示出来而不是 catch 掉——
 *    catch 掉的表现是"点了没反应"，而那正是本仓修过一次的 window.confirm 坑
 *    （ReviewHistoryPage 的注释里有记录）的同一种形态。
 */
export default function LanguageSwitcher({ variant = 'header' }: { variant?: 'header' | 'drawer' }) {
  const locale = useLocale()
  const [open, setOpen] = useState(false)
  const [failed, setFailed] = useState(false)
  const [pending, setPending] = useState<Locale | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)

  // Esc 收起。与账户菜单同一套交互，用户不用学两遍。
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  // 只有一种语言 = 没有可切的东西。见文件头第 1 条。
  if (LOCALES.length <= 1) return null

  const choose = (next: Locale) => {
    if (next === getLocale()) {
      setOpen(false)
      return
    }
    setPending(next)
    setFailed(false)
    void setLocale(next)
      .then(() => setOpen(false))
      .catch((e) => {
        console.error('[i18n] 切换语言失败', e)
        setFailed(true)
      })
      .finally(() => setPending(null))
  }

  const items = LOCALES.map((l) => (
    <button
      key={l}
      onClick={() => choose(l)}
      disabled={pending !== null}
      lang={l}
      className={cn(
        'flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-sm transition-colors disabled:opacity-60',
        l === locale
          ? 'text-text-primary'
          : 'text-text-secondary hover:bg-bg-card-hover hover:text-text-primary',
      )}
      aria-current={l === locale}
    >
      <span>{LOCALE_ENDONYM[l]}</span>
      {l === locale && <Check className="h-3.5 w-3.5 shrink-0" strokeWidth={2} />}
    </button>
  ))

  if (variant === 'drawer') {
    // 抽屉里不用下拉——移动端叠一层浮层容易点不中，直接平铺两三行更省事。
    return (
      <div className="mt-2 border-t border-black/5 pt-2">
        <p className="px-4 py-1 text-xs text-text-muted">{t('common.ui.language')}</p>
        <div className="px-1">{items}</div>
        <p className="px-4 pb-1 pt-0.5 text-[11px] leading-relaxed text-text-muted">
          {t('common.ui.language_hint')}
        </p>
        {failed && (
          <p className="px-4 py-1 text-[11px] text-severity-critical">{t('common.ui.error')}</p>
        )}
      </div>
    )
  }

  return (
    <div className="relative shrink-0" ref={boxRef}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 rounded-lg px-2 py-2 text-sm whitespace-nowrap text-text-secondary transition-all hover:text-text-primary"
        aria-label={t('common.ui.language_aria')}
        aria-expanded={open}
        title={t('common.ui.language')}
      >
        <Globe className="h-4 w-4" strokeWidth={1.5} />
        {/* 只显示图标 + 两字母码，顶栏已经很挤了，不放完整语言名 */}
        <span className="text-[11px] font-medium uppercase tracking-wide">{locale}</span>
      </button>
      {open && (
        <>
          {/* 点击空白处收起——与账户菜单同一种做法 */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-2 w-52 rounded-2xl border border-black/[0.06] bg-bg-card p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.12)]">
            {items}
            <p className="px-3 pb-1 pt-1.5 text-[11px] leading-relaxed text-text-muted">
              {t('common.ui.language_hint')}
            </p>
            {failed && (
              <p className="px-3 pb-1 text-[11px] text-severity-critical">{t('common.ui.error')}</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
