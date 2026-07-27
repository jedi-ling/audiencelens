import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import './landing.css'
import './landing-in-app.css' // hero 顶距等适配，与共享 Layout 拼接用
// landing-body.html / landing.css 就是落地页的正文本体——直接改这两个文件即可，
// 不再有独立的静态设计源（曾经有过，已下线；本 React 版就是唯一权威版本）。
import landingBody from './landing-body.html?raw'

/**
 * 营销落地页 —— 作为 `/` 路由，与 app 共用同一套 Layout（导航/页脚），
 * 金色主题与 app 内部的 neon-green 界面刻意区分。
 * 正文走 dangerouslySetInnerHTML + 作用域化到 .al-landing 的 CSS，
 * 交互脚本在下面的 useEffect 里，内部链接已改成 React Router 跳转，实现 SPA 无刷新链路。
 */
export default function LandingPage() {
  const rootRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const cleanups: Array<() => void> = []

    // 导航滚动态
    const navEl = root.querySelector<HTMLElement>('#nav')
    const onScroll = () => navEl?.classList.toggle('scrolled', window.scrollY > 24)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    cleanups.push(() => window.removeEventListener('scroll', onScroll))

    // 移动端菜单
    const toggle = root.querySelector<HTMLElement>('#navToggle')
    const links = root.querySelector<HTMLElement>('#navLinks')
    const onToggle = () => links?.classList.toggle('open')
    const onLinksClick = (e: Event) => {
      if ((e.target as HTMLElement).tagName === 'A') links?.classList.remove('open')
    }
    toggle?.addEventListener('click', onToggle)
    links?.addEventListener('click', onLinksClick)
    cleanups.push(() => {
      toggle?.removeEventListener('click', onToggle)
      links?.removeEventListener('click', onLinksClick)
    })

    // 统一链接拦截：# 锚点页内平滑滚动；/ 开头内部路由走 SPA；http/_blank 外链放行
    const onRootClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement).closest('a')
      if (!a) return
      const href = a.getAttribute('href') || ''
      if (a.getAttribute('target') === '_blank' || /^https?:/.test(href)) return
      if (href.startsWith('#')) {
        if (href.length < 2) return
        const el = root.querySelector(href)
        if (el) {
          e.preventDefault()
          el.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
        return
      }
      if (href.startsWith('/')) {
        e.preventDefault()
        navigate(href)
      }
    }
    root.addEventListener('click', onRootClick)
    cleanups.push(() => root.removeEventListener('click', onRootClick))

    // 示例 chips → 带着文案跳对话评审入口。
    // 两组文案风格不同：hero 顶部 .chips 是名词短语（"Steam 商店页"），需要拼前缀；
    // 输入框下方 .chips-examples 是完整祈使句（"评审我的 Steam 商店页"），直接透传，
    // 否则会拼成"帮我评审一下我的评审我的 Steam 商店页"这种病句。
    const chipHandlers: Array<[Element, () => void]> = []
    root.querySelectorAll<HTMLElement>('.chip').forEach((c) => {
      const isExample = c.closest('.chips-examples') !== null
      const h = () => {
        const text = (c.textContent || '').trim()
        const q = isExample ? text : '帮我评审一下我的' + text
        navigate('/ask?q=' + encodeURIComponent(q))
      }
      c.addEventListener('click', h)
      chipHandlers.push([c, h])
    })
    cleanups.push(() => chipHandlers.forEach(([c, h]) => c.removeEventListener('click', h)))

    // 首页直接对话：单行输入条提交后带着内容跳去 /ask（SPA 内跳转，不刷新）
    const heroAsk = root.querySelector<HTMLFormElement>('#heroAsk')
    const heroAskInput = root.querySelector<HTMLInputElement>('#heroAskInput')
    const onHeroAskSubmit = (e: Event) => {
      e.preventDefault()
      const val = (heroAskInput?.value || '').trim()
      navigate(val ? '/ask?q=' + encodeURIComponent(val) : '/ask')
    }
    heroAsk?.addEventListener('submit', onHeroAskSubmit)
    cleanups.push(() => heroAsk?.removeEventListener('submit', onHeroAskSubmit))

    // 滚动渐显
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (en.isIntersecting) {
            en.target.classList.add('in')
            io.unobserve(en.target)
          }
        })
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    )
    root.querySelectorAll('.reveal').forEach((el) => io.observe(el))
    cleanups.push(() => io.disconnect())

    // P0-3：辩论卡片 stagger 入场（反对→翻票→赞同），尊重 prefers-reduced-motion
    // 仅在 hero 首次进入视口时触发一次，避免反复播放
    const debateCard = root.querySelector<HTMLElement>('.debate-card')
    if (debateCard) {
      const opposeEl = debateCard.querySelector<HTMLElement>('.debate-msg.oppose')
      const flipEl = debateCard.querySelector<HTMLElement>('.debate-flip')
      const agreeEl = debateCard.querySelector<HTMLElement>('.debate-msg.agree')
      const debateTargets = [opposeEl, flipEl, agreeEl].filter(Boolean) as HTMLElement[]
      const debateTimers: number[] = []
      const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches
      if (!reduceMotion) {
        // 初始隐藏，等待 IntersectionObserver 触发入场
        debateTargets.forEach((el) => el.classList.add('debate-stagger'))
        const debateIo = new IntersectionObserver(
          (entries) => {
            const en = entries[0]
            if (!en.isIntersecting) return
            debateIo.disconnect()
            // 反对 200ms / 翻票 600ms / 赞同 1000ms 的 stagger 节奏
            const delays = [200, 600, 1000]
            debateTargets.forEach((el, idx) => {
              const t = window.setTimeout(() => el.classList.add('debate-stagger-in'), delays[idx] || 0)
              debateTimers.push(t)
            })
          },
          { threshold: 0.25 },
        )
        debateIo.observe(debateCard)
        cleanups.push(() => {
          debateTimers.forEach((t) => window.clearTimeout(t))
          debateIo.disconnect()
        })
      }
    }

    // 数字计数（HTML 默认已是真数字，动画作增强）
    const counted = new WeakSet<Element>()
    const co = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (!en.isIntersecting || counted.has(en.target)) return
          counted.add(en.target)
          const el = en.target as HTMLElement
          const target = parseInt(el.dataset.target || '0', 10)
          const dur = 1400
          let t0: number | null = null
          const step = (ts: number) => {
            if (!t0) t0 = ts
            const p = Math.min((ts - t0) / dur, 1)
            const e = 1 - Math.pow(1 - p, 3)
            el.textContent = String(Math.floor(e * target))
            if (p < 1) requestAnimationFrame(step)
            else el.textContent = String(target)
          }
          requestAnimationFrame(step)
        })
      },
      { threshold: 0.5 },
    )
    root.querySelectorAll<HTMLElement>('.num[data-target]').forEach((el) => co.observe(el))
    cleanups.push(() => co.disconnect())

    // Hero 金色粒子（限 30fps + 滚出视口暂停）
    const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches
    const canvas = root.querySelector<HTMLCanvasElement>('#heroCanvas')
    const hero = canvas?.closest('.hero') as HTMLElement | null
    if (canvas && hero && !reduce) {
      const ctx = canvas.getContext('2d')
      if (ctx) {
        const size = () => {
          canvas.width = hero.offsetWidth
          canvas.height = hero.offsetHeight
        }
        size()
        window.addEventListener('resize', size)
        cleanups.push(() => window.removeEventListener('resize', size))

        type Pt = { x: number; y: number; vx: number; vy: number; r: number; a: number }
        const parts: Pt[] = []
        for (let i = 0; i < 46; i++)
          parts.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.22,
            vy: (Math.random() - 0.5) * 0.22,
            r: Math.random() * 1.4 + 0.4,
            a: Math.random() * 0.35 + 0.12,
          })
        let running = false
        let last = 0
        let raf = 0
        const FRAME = 1000 / 30
        const tick = (now: number) => {
          if (!running) return
          raf = requestAnimationFrame(tick)
          if (now - last < FRAME) return
          last = now
          ctx.clearRect(0, 0, canvas.width, canvas.height)
          for (let i = 0; i < parts.length; i++) {
            const a = parts[i]
            a.x += a.vx
            a.y += a.vy
            if (a.x < 0 || a.x > canvas.width) a.vx *= -1
            if (a.y < 0 || a.y > canvas.height) a.vy *= -1
            ctx.beginPath()
            ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2)
            ctx.fillStyle = 'rgba(183,126,59,' + a.a + ')'
            ctx.fill()
            for (let j = i + 1; j < parts.length; j++) {
              const b = parts[j]
              const dx = a.x - b.x
              const dy = a.y - b.y
              const d = Math.sqrt(dx * dx + dy * dy)
              if (d < 130) {
                ctx.beginPath()
                ctx.moveTo(a.x, a.y)
                ctx.lineTo(b.x, b.y)
                ctx.strokeStyle = 'rgba(183,126,59,' + (1 - d / 130) * 0.06 + ')'
                ctx.lineWidth = 0.5
                ctx.stroke()
              }
            }
          }
        }
        const startAnim = () => {
          if (!running) {
            running = true
            raf = requestAnimationFrame(tick)
          }
        }
        const stopAnim = () => {
          running = false
          if (raf) cancelAnimationFrame(raf)
        }
        const heroIo = new IntersectionObserver((es) => (es[0].isIntersecting ? startAnim() : stopAnim()), {
          threshold: 0,
        })
        heroIo.observe(hero)
        cleanups.push(() => {
          stopAnim()
          heroIo.disconnect()
        })
      }
    }

    // 从别的路由进来时回到顶部
    window.scrollTo(0, 0)

    return () => cleanups.forEach((fn) => fn())
  }, [navigate])

  return <div className="al-landing" ref={rootRef} dangerouslySetInnerHTML={{ __html: landingBody }} />
}
