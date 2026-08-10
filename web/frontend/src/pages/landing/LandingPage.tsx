import { lazy, Suspense, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { createRoot } from 'react-dom/client'
import './landing.css'
import './landing-in-app.css' // hero 顶距等适配，与共享 Layout 拼接用

// lazy：three.js 约 150KB gzip，绝不能进主包——app 内部页面一行都用不到它
const HeroScene = lazy(() => import('./HeroScene'))

/** 挂载点 → 已创建的 root。同一个节点重复 createRoot 会让两套场景同时活着
 *  （StrictMode 下 effect 跑两次，而 unmount 是异步的，第二次 createRoot 抢在前面）。
 *  实测控制台会报 "container that has already been passed to createRoot"，
 *  代价不是一条警告，是**两份 26000 粒子的场景同时在渲染**。 */
const stageRoots = new WeakMap<HTMLElement, ReturnType<typeof createRoot>>()
/** 挂载世代。StrictMode 下 effect 跑两次，而清理被推到微任务里执行——
 *  第一次的清理会晚于第二次挂载，把刚渲染好的场景又清空（实测：canvas 数 0）。
 *  记一个世代号，只有"仍是最新那次"的清理才真正生效。 */
const stageGen = new WeakMap<HTMLElement, number>()
// landing-body.html / landing.css 就是落地页的正文本体——直接改这两个文件即可，
// 不再有独立的静态设计源（曾经有过，已下线；本 React 版就是唯一权威版本）。
import landingBody from './landing-body.html?raw'

/**
 * 营销落地页 —— 作为 `/` 路由，与 app 共用同一套 Layout（导航/页脚）。
 *
 * 配色与 app 内部**完全一致**：landing.css 的 --gold 和 index.css 的
 * --color-brand-primary 都是 Apple 系统蓝 #0071e3，--gold-bright 是亮蓝 #2997ff。
 * 落地页之所以还留着自己一套 CSS 变量，只是因为它的样式作用域
 * 化在 .al-landing 里、不走 Tailwind token，不是因为要走另一套视觉。
 * 2026-08 全站由暗色古铜金统一改为浅色苹果风（见 index.css @theme 头部注释）。
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

    // Hero 视频背景：autoplay 属性会被部分环境拦截，这里强制补一次 play()。
    // muted + playsinline 已满足浏览器自动播放策略，重复 play() 无副作用。
    //
    // P1-11：prefers-reduced-motion 或窄屏（≤640px，与 HeroScene 3D 场景
    // ≤920px 不挂载的先例一致，这里更保守一档因为视频还有网络流量成本）
    // 时直接不播放。不用 CSS display:none——那样浏览器仍会继续下载/解码，
    // 起不到省流量的作用；这里连 <source> 一并摘掉、调 load() 释放资源，
    // 摘掉 source 后 poster 帧会一直顶在原地。
    const heroVideo = root.querySelector<HTMLVideoElement>('video.hero-bg-video')
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const isNarrowViewport = window.innerWidth <= 640
    if (heroVideo && (prefersReducedMotion || isNarrowViewport)) {
      heroVideo.pause()
      heroVideo.removeAttribute('autoplay')
      heroVideo.querySelectorAll('source').forEach((s) => s.remove())
      heroVideo.load()
    } else {
      const onVideoCanPlay = () => { heroVideo?.play().catch(() => {}) }
      heroVideo?.addEventListener('canplay', onVideoCanPlay)
      heroVideo?.play().catch(() => {})
      cleanups.push(() => heroVideo?.removeEventListener('canplay', onVideoCanPlay))
    }

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

    // 图片加载失败时隐藏图标。原先走内联 onerror，但内联事件处理器会被严格 CSP
    // 的 script-src 拦截，改由这里挂 error 监听（HIGH-3）。
    const imgHandlers: Array<[HTMLImageElement, () => void]> = []
    root.querySelectorAll<HTMLImageElement>('img.ico').forEach((img) => {
      const h = () => {
        img.style.display = 'none'
      }
      img.addEventListener('error', h)
      imgHandlers.push([img, h])
    })
    cleanups.push(() => imgHandlers.forEach(([img, h]) => img.removeEventListener('error', h)))

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

    // P0-3：争议点摘要卡片 stagger 入场（反方→配对分隔→正方），尊重 prefers-reduced-motion
    // 仅在 hero 首次进入视口时触发一次，避免反复播放。
    // 类名沿用历史的 .debate-* / .debate-flip（CSS 里同名，不改）。
    // 这张卡是**示意图 + 样例数据**，不是某次真实评审的截图，文案里已标注。
    // 口径更新：cross_exam.py 现在会真的发反驳调用（standard 档 1 次仲裁式、
    // full 档每位涉事人格各 1 次），改票由代码比较反驳前后的立场与置信度判定。
    // 但仍然**只有一轮**——改文案时不要写成"多轮辩论"，也不要用"多智能体辩论"
    // 笼统盖过 standard 档（那一档是仲裁式，不是各自独立发言）。
    // quick 档一次反驳调用都不发，无 api_key 时同样不发。
    const debateCard = root.querySelector<HTMLElement>('.debate-card')
    if (debateCard) {
      const opposeEl = debateCard.querySelector<HTMLElement>('.debate-msg.oppose')
      const pairEl = debateCard.querySelector<HTMLElement>('.debate-flip')
      const agreeEl = debateCard.querySelector<HTMLElement>('.debate-msg.agree')
      const debateTargets = [opposeEl, pairEl, agreeEl].filter(Boolean) as HTMLElement[]
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
            // 反方 200ms / 配对分隔 600ms / 正方 1000ms 的 stagger 节奏
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
    // P1-12：其余动效（reveal、debate-stagger、three 粒子）都已经查
    // prefers-reduced-motion，这个计数动画之前漏了——直接赋最终值，不跑
    // requestAnimationFrame 循环。
    const prefersReducedMotionForCount = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const counted = new WeakSet<Element>()
    const co = new IntersectionObserver(
      (entries) => {
        entries.forEach((en) => {
          if (!en.isIntersecting || counted.has(en.target)) return
          counted.add(en.target)
          const el = en.target as HTMLElement
          const target = parseInt(el.dataset.target || '0', 10)
          if (prefersReducedMotionForCount) {
            el.textContent = String(target)
            return
          }
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

    // Hero 3D 舞台的挂载点。正文是 dangerouslySetInnerHTML 注进来的，
    // 所以这里拿到节点后交给 createPortal，让 React 正常管理这棵子树的生命周期。
    //
    // 这里原本是 46 个浮动小圆点 + 连线——全互联网最泛滥的 SaaS 背景效果，
    // 它不传达任何关于"多角色评审"的信息，谁家都能用。换成能说清产品是什么的东西。
    // Hero 3D 舞台：在这里**命令式**挂一个独立 React root，不走 state + portal。
    //
    // 为什么不能用 state+portal（第一版就是那么写的，症状极其隐蔽）：
    // 正文是 dangerouslySetInnerHTML 注进来的。setStageEl 会触发父组件重渲染，
    // React 重新应用 innerHTML → **原来的挂载节点被销毁重建**，而 portal 仍然
    // 往那个已脱离文档的旧节点里渲染。组件正常渲染、effect 正常执行、控制台零报错，
    // 页面上什么都没有。实测 host 的 document.contains(host) === false 才定位到。
    //
    // 命令式挂载没有这个耦合：不产生 state 更新 → 不重渲染 → innerHTML 不会被重设，
    // 节点身份从头到尾稳定。
    const stageMount = root.querySelector<HTMLElement>('#heroStageMount')
    if (stageMount) {
      // 复用已有 root 而不是新建：见 stageRoots 的说明。
      let stageRoot = stageRoots.get(stageMount)
      if (!stageRoot) {
        stageRoot = createRoot(stageMount)
        stageRoots.set(stageMount, stageRoot)
      }
      const r = stageRoot
      const gen = (stageGen.get(stageMount) ?? 0) + 1
      stageGen.set(stageMount, gen)
      stageRoot.render(
        <Suspense fallback={null}>
          <HeroScene />
        </Suspense>,
      )
      // 卸载推到微任务：在父组件 cleanup 里同步卸载子 root 会触发
      // "正在渲染时同步卸载" 警告。同时把注册表清掉，避免 WeakMap 里
      // 留一个已卸载的 root 被下次误复用。
      // 卸载走 render(null) 而不是 unmount()：
      // root 一旦 unmount，同一个 DOM 节点就再也不能安全地 createRoot——
      // React 内部记着这个容器，第二次创建会报
      // "container that has already been passed to createRoot"，
      // 而且两个 root 会同时活着（两份 26000 粒子的场景一起渲染）。
      // render(null) 会正常卸载 HeroScene（触发它的 effect cleanup → 释放 three
      // 的 renderer/geometry/material），同时把 root 留着给下次复用。
      // root 本身随 DOM 节点被 GC —— stageRoots 是 WeakMap，不会泄漏。
      cleanups.push(() =>
        queueMicrotask(() => {
          // 已经有更新的挂载了 → 这次清理是过期的，不能动
          if (stageGen.get(stageMount) === gen) r.render(null)
        }),
      )
    }

    // 从别的路由进来时回到顶部
    window.scrollTo(0, 0)

    return () => cleanups.forEach((fn) => fn())
  }, [navigate])

  return <div className="al-landing" ref={rootRef} dangerouslySetInnerHTML={{ __html: landingBody }} />
}
