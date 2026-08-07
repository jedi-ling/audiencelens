/**
 * Hero 全幅背景：72 个视角环绕一份材料。
 *
 * 概念与标题咬合：主标题写"让 72 个 AI 评审员…"，背景就真的是 72 个视角节点
 * 在球面上环绕中心那叠材料。这个数字不是随手取的，是同一个事实。
 *
 * 第一版做成了右侧一个 348×300 的小卡片：白板 + 几根线塞在框里，
 * 既没有气势也不专业。全幅背景才立得住——但代价是它必须**不抢**：
 *   · pointer-events:none —— 绝不劫持 hero 里的输入框和按钮；
 *   · 左侧文案区做遮罩收淡 —— 正文对比度不能被背景吃掉；
 *   · 鼠标视差代替拖拽 —— 背景该回应，不该被操作。
 *
 * 性能约束（都在代码里落实，不只写在注释里）：
 *   1. three 只在组件挂载时 import()，不进主包；
 *   2. prefers-reduced-motion → 只画一帧静态构图；
 *   3. 移出视口 → 停掉渲染循环；
 *   4. ≤920px 不挂载（CSS 与这里的宽度判断双保险）。
 */

import { useEffect, useRef, useState } from 'react'

/** 视角总数——与首页主标题里的人格数是同一个事实 */
const VIEWPOINT_COUNT = 72
/** 每隔几个节点画一条视线。72 条会糊成毛球，只连一部分才有"注视"的意思 */
const SIGHTLINE_EVERY = 4
/** 分歧方（暖橙）的间隔。评审团里总有少数派，这正是产品的卖点 */
const DISSENT_EVERY = 9

export default function HeroScene() {
  const hostRef = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    // 窄屏不挂载：手机上这层背景既看不清，也不值那份电量与流量
    if (window.innerWidth <= 920) return

    let disposed = false
    const cleanups: Array<() => void> = []

    void (async () => {
      let THREE: typeof import('three')
      try {
        THREE = await import('three')
      } catch {
        if (!disposed) setFailed(true)
        return
      }
      if (disposed || !hostRef.current) return

      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
      const w = () => host.clientWidth || 1
      const h = () => host.clientHeight || 1

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setSize(w(), h())
      renderer.outputColorSpace = THREE.SRGBColorSpace
      host.appendChild(renderer.domElement)

      const scene = new THREE.Scene()
      // 雾把远端节点压淡——这层背景"有纵深而不喧宾夺主"全靠它。
      // 没有雾，72 个点会平铺成一张噪点图，正文压上去就脏了。
      scene.fog = new THREE.Fog(0xf5f5f7, 9, 21)

      const camera = new THREE.PerspectiveCamera(34, w() / h(), 0.1, 100)
      camera.position.set(0, 0.4, 12.5)

      const rig = new THREE.Group()
      // 整体右移：左侧留给文案，重心落在右侧，与双栏布局同一根轴线
      rig.position.x = 2.6
      scene.add(rig)

      // ---- 中心：一叠材料。三张薄板错开，比单块白板更像"一份要被审的东西" ----
      const paper = new THREE.Group()
      const sheetGeo = new THREE.PlaneGeometry(2.05, 2.75)
      const sheets = [
        { z: -0.09, o: 0.3, y: -0.055 },
        { z: 0, o: 0.52, y: 0 },
        { z: 0.09, o: 0.86, y: 0.055 },
      ]
      sheets.forEach((s) => {
        const m = new THREE.Mesh(
          sheetGeo,
          new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: s.o,
            side: THREE.DoubleSide,
            depthWrite: false,
          }),
        )
        m.position.set(0, s.y, s.z)
        paper.add(m)
        // 每张纸一圈细边：纯白面在浅色背景上会糊掉，边线把形定住
        const edge = new THREE.LineSegments(
          new THREE.EdgesGeometry(sheetGeo),
          new THREE.LineBasicMaterial({
            color: 0x0071e3,
            transparent: true,
            opacity: s.o * 0.55,
          }),
        )
        edge.position.copy(m.position)
        paper.add(edge)
      })
      paper.rotation.set(-0.06, 0.34, 0.02)
      rig.add(paper)

      // ---- 72 个视角：球面均匀分布（黄金角螺旋），不是一圈平铺 ----
      const R = 5.0
      const positions = new Float32Array(VIEWPOINT_COUNT * 3)
      const colors = new Float32Array(VIEWPOINT_COUNT * 3)
      const golden = Math.PI * (3 - Math.sqrt(5))
      const linePts: number[] = []
      const lineCols: number[] = []
      const brand = new THREE.Color(0x0071e3)
      const dissent = new THREE.Color(0xff9f0a)

      for (let i = 0; i < VIEWPOINT_COUNT; i++) {
        const y = 1 - (i / (VIEWPOINT_COUNT - 1)) * 2
        const r = Math.sqrt(Math.max(0, 1 - y * y))
        const th = golden * i
        const p = new THREE.Vector3(Math.cos(th) * r, y, Math.sin(th) * r).multiplyScalar(R)
        positions.set([p.x, p.y, p.z], i * 3)

        const c = i % DISSENT_EVERY === 0 ? dissent : brand
        colors.set([c.r, c.g, c.b], i * 3)

        if (i % SIGHTLINE_EVERY === 0) {
          const near = p.clone().multiplyScalar(0.29) // 只连到材料表面，不穿过去
          linePts.push(p.x, p.y, p.z, near.x, near.y, near.z)
          lineCols.push(c.r, c.g, c.b, c.r, c.g, c.b)
        }
      }

      const nodeGeo = new THREE.BufferGeometry()
      nodeGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      nodeGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3))

      // 圆形光点贴图：默认方形 point 在浅底上像一堆像素噪点，圆点才干净
      const dot = (() => {
        const c = document.createElement('canvas')
        c.width = 64
        c.height = 64
        const g = c.getContext('2d')!
        const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32)
        grd.addColorStop(0, 'rgba(255,255,255,1)')
        grd.addColorStop(0.45, 'rgba(255,255,255,.92)')
        grd.addColorStop(1, 'rgba(255,255,255,0)')
        g.fillStyle = grd
        g.fillRect(0, 0, 64, 64)
        const t = new THREE.CanvasTexture(c)
        t.colorSpace = THREE.SRGBColorSpace
        return t
      })()

      const nodeMat = new THREE.PointsMaterial({
        size: 0.19,
        map: dot,
        vertexColors: true,
        transparent: true,
        opacity: 0.85,
        sizeAttenuation: true,
        depthWrite: false,
        fog: true,
      })
      rig.add(new THREE.Points(nodeGeo, nodeMat))

      const lineGeo = new THREE.BufferGeometry()
      lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePts, 3))
      lineGeo.setAttribute('color', new THREE.Float32BufferAttribute(lineCols, 3))
      const lineMat = new THREE.LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.16, // 压得很低：这是背景，不是图表
        fog: true,
      })
      rig.add(new THREE.LineSegments(lineGeo, lineMat))

      // ---- 交互：鼠标视差。背景该**回应**，不该被操作——
      //      canvas 是 pointer-events:none，所以监听挂在 window 上。 ----
      let mx = 0
      let my = 0
      const onMouse = (e: MouseEvent) => {
        mx = (e.clientX / window.innerWidth - 0.5) * 2
        my = (e.clientY / window.innerHeight - 0.5) * 2
      }
      if (!reduce) {
        window.addEventListener('mousemove', onMouse, { passive: true })
        cleanups.push(() => window.removeEventListener('mousemove', onMouse))
      }

      const resize = () => {
        camera.aspect = w() / h()
        camera.updateProjectionMatrix()
        renderer.setSize(w(), h())
      }
      const ro = new ResizeObserver(resize)
      ro.observe(host)
      cleanups.push(() => ro.disconnect())

      let spin = 0
      const draw = () => {
        // 视差用缓动跟随而不是直接赋值——直接赋值会让整个画面跟着鼠标抖
        rig.rotation.y += (spin + mx * 0.2 - rig.rotation.y) * 0.04
        rig.rotation.x += (-my * 0.1 - rig.rotation.x) * 0.04
        paper.rotation.y += (0.34 + mx * 0.09 - paper.rotation.y) * 0.05
        renderer.render(scene, camera)
      }

      if (reduce) {
        spin = 0.35
        rig.rotation.y = 0.35
        draw()
        cleanups.push(() => renderer.dispose())
        return
      }

      // 先同步画一帧：rAF 首帧可能被推迟，那期间用户看到的是一块空白
      draw()

      let raf = 0
      let visible = true
      const tick = () => {
        raf = requestAnimationFrame(tick)
        if (!visible) return
        spin += 0.0011 // 慢到几乎察觉不到，停留几秒才会发现它在动
        draw()
      }
      raf = requestAnimationFrame(tick)
      cleanups.push(() => cancelAnimationFrame(raf))

      const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting }, {
        threshold: 0.01,
      })
      io.observe(host)
      cleanups.push(() => io.disconnect())

      cleanups.push(() => {
        renderer.dispose()
        sheetGeo.dispose()
        nodeGeo.dispose()
        lineGeo.dispose()
        nodeMat.dispose()
        lineMat.dispose()
        dot.dispose()
        const el = renderer.domElement
        if (el.parentNode) el.parentNode.removeChild(el)
      })
    })()

    return () => {
      disposed = true
      cleanups.forEach((fn) => fn())
    }
  }, [])

  return (
    <div className="hero-bg3d" aria-hidden="true">
      <div ref={hostRef} className="hero-bg3d-canvas" />
      {failed && <div className="hero-bg3d-fallback" />}
    </div>
  )
}
