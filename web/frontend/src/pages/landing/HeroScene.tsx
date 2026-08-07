/**
 * Hero 全幅深色舞台：72 个视角环绕一份材料，视线上有数据流动。
 *
 * 为什么这一版把 hero 改成深色：发光、辉光、流光这些真正有冲击力的效果
 * 全靠加色混合（AdditiveBlending），而加色在白底上直接隐形——浅底上做不出光。
 * 前两版效果"太弱"的根因就是这个。深色 hero + 浅色正文是 Linear / Vercel
 * 这类站的标准打法，冲击力和专业感都在这一步。深色只作用于 hero，
 * 页面其余部分仍是原来的浅色。
 *
 * 概念与标题咬合：主标题"让 72 个 AI 评审员…"，背景就真的是 72 个视角节点
 * 按黄金角螺旋环绕中心那叠材料。每隔几个是暖橙的分歧方，视线上有粒子
 * 从节点流向材料——"72 双眼睛正在看这份东西"。
 *
 * 性能与降级（都在代码里落实）：
 *   1. three 只在组件挂载时 import()，不进主包；
 *   2. prefers-reduced-motion → 画一帧静态构图，不起 RAF；
 *   3. 移出视口 → 停掉渲染循环；
 *   4. ≤920px 不挂载（CSS 与这里的宽度判断双保险）。
 */

import { useEffect, useRef, useState } from 'react'

/** 视角总数——与首页主标题里的人格数是同一个事实 */
const VIEWPOINT_COUNT = 72
/** 每隔几个节点画一条视线 + 一颗流动粒子。全连会糊成毛球 */
const SIGHTLINE_EVERY = 3
/** 分歧方（暖橙）的间隔。评审团里总有少数派，这正是产品的卖点 */
const DISSENT_EVERY = 8

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
      // 雾用深色，把远端压进暗处——纵深感和"不喧宾夺主"都靠它。
      // 颜色对齐 CSS 里 hero-bg3d 的深色底，边缘才不露缝。
      scene.fog = new THREE.Fog(0x0a1024, 10, 26)

      const camera = new THREE.PerspectiveCamera(36, w() / h(), 0.1, 100)
      camera.position.set(0, 0.5, 13)

      const rig = new THREE.Group()
      rig.position.x = 2.4 // 右移，左侧留给文案
      scene.add(rig)

      const brand = new THREE.Color(0x2997ff) // 深底上用更亮的蓝，才发得出光
      const dissent = new THREE.Color(0xffb340)

      // ---- 中心：一叠发光材料。三张错开的薄板 + 亮边 ----
      const paper = new THREE.Group()
      const sheetGeo = new THREE.PlaneGeometry(2.1, 2.8)
      const sheets = [
        { z: -0.1, o: 0.1, y: -0.06 },
        { z: 0, o: 0.16, y: 0 },
        { z: 0.1, o: 0.24, y: 0.06 },
      ]
      sheets.forEach((s) => {
        const m = new THREE.Mesh(
          sheetGeo,
          new THREE.MeshBasicMaterial({
            color: 0x8fc8ff,
            transparent: true,
            opacity: s.o,
            side: THREE.DoubleSide,
            depthWrite: false,
          }),
        )
        m.position.set(0, s.y, s.z)
        paper.add(m)
        const edge = new THREE.LineSegments(
          new THREE.EdgesGeometry(sheetGeo),
          new THREE.LineBasicMaterial({
            color: 0x5cb0ff,
            transparent: true,
            opacity: 0.5 + s.o,
          }),
        )
        edge.position.copy(m.position)
        paper.add(edge)
      })
      paper.rotation.set(-0.05, 0.36, 0.02)
      rig.add(paper)

      // ---- 72 个视角：球面黄金角螺旋 ----
      const R = 5.2
      const nodePos: import('three').Vector3[] = []
      const nodeColArr = new Float32Array(VIEWPOINT_COUNT * 3)
      const nodeXYZ = new Float32Array(VIEWPOINT_COUNT * 3)
      const golden = Math.PI * (3 - Math.sqrt(5))
      const linePts: number[] = []
      const lineCols: number[] = []
      const streams: { from: import('three').Vector3; to: import('three').Vector3; col: import('three').Color; phase: number }[] = []

      for (let i = 0; i < VIEWPOINT_COUNT; i++) {
        const y = 1 - (i / (VIEWPOINT_COUNT - 1)) * 2
        const r = Math.sqrt(Math.max(0, 1 - y * y))
        const th = golden * i
        const p = new THREE.Vector3(Math.cos(th) * r, y, Math.sin(th) * r).multiplyScalar(R)
        nodePos.push(p)
        nodeXYZ.set([p.x, p.y, p.z], i * 3)
        const c = i % DISSENT_EVERY === 0 ? dissent : brand
        nodeColArr.set([c.r, c.g, c.b], i * 3)

        if (i % SIGHTLINE_EVERY === 0) {
          const near = p.clone().multiplyScalar(0.3)
          linePts.push(p.x, p.y, p.z, near.x, near.y, near.z)
          // 视线渐隐：节点端亮、材料端暗
          lineCols.push(c.r, c.g, c.b, c.r * 0.2, c.g * 0.2, c.b * 0.2)
          streams.push({ from: p, to: near, col: c, phase: Math.random() })
        }
      }

      // 圆形辉光贴图：加色混合下，中心亮、边缘散，才是"光"而不是"点"
      const glow = (() => {
        const c = document.createElement('canvas')
        c.width = 128
        c.height = 128
        const g = c.getContext('2d')!
        const grd = g.createRadialGradient(64, 64, 0, 64, 64, 64)
        grd.addColorStop(0, 'rgba(255,255,255,1)')
        grd.addColorStop(0.2, 'rgba(255,255,255,.85)')
        grd.addColorStop(0.5, 'rgba(255,255,255,.28)')
        grd.addColorStop(1, 'rgba(255,255,255,0)')
        g.fillStyle = grd
        g.fillRect(0, 0, 128, 128)
        const t = new THREE.CanvasTexture(c)
        t.colorSpace = THREE.SRGBColorSpace
        return t
      })()

      // ---- 节点（发光） ----
      const nodeGeo = new THREE.BufferGeometry()
      nodeGeo.setAttribute('position', new THREE.BufferAttribute(nodeXYZ, 3))
      nodeGeo.setAttribute('color', new THREE.BufferAttribute(nodeColArr, 3))
      const nodeMat = new THREE.PointsMaterial({
        size: 0.42,
        map: glow,
        vertexColors: true,
        transparent: true,
        opacity: 0.95,
        sizeAttenuation: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending, // 光的关键：叠加而非覆盖
        fog: true,
      })
      const nodePoints = new THREE.Points(nodeGeo, nodeMat)
      rig.add(nodePoints)

      // ---- 视线 ----
      const lineGeo = new THREE.BufferGeometry()
      lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePts, 3))
      lineGeo.setAttribute('color', new THREE.Float32BufferAttribute(lineCols, 3))
      const lineMat = new THREE.LineBasicMaterial({
        vertexColors: true,
        transparent: true,
        opacity: 0.32,
        blending: THREE.AdditiveBlending,
        fog: true,
      })
      rig.add(new THREE.LineSegments(lineGeo, lineMat))

      // ---- 数据流：粒子从节点流向材料。这是"正在审视"的动词 ----
      const streamXYZ = new Float32Array(streams.length * 3)
      const streamCol = new Float32Array(streams.length * 3)
      streams.forEach((s, i) => streamCol.set([s.col.r, s.col.g, s.col.b], i * 3))
      const streamGeo = new THREE.BufferGeometry()
      streamGeo.setAttribute('position', new THREE.BufferAttribute(streamXYZ, 3))
      streamGeo.setAttribute('color', new THREE.BufferAttribute(streamCol, 3))
      const streamMat = new THREE.PointsMaterial({
        size: 0.3,
        map: glow,
        vertexColors: true,
        transparent: true,
        opacity: 1,
        sizeAttenuation: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        fog: true,
      })
      const streamPoints = new THREE.Points(streamGeo, streamMat)
      rig.add(streamPoints)

      // ---- 轨道环：两道细环，暗示"围绕审视"的秩序 ----
      const ringMat = new THREE.LineBasicMaterial({
        color: 0x2997ff,
        transparent: true,
        opacity: 0.12,
        blending: THREE.AdditiveBlending,
        fog: true,
      })
      const rings: import('three').Line[] = []
      ;[{ r: R * 0.98, tilt: 1.15 }, { r: R * 1.04, tilt: -0.5 }].forEach((cfg) => {
        const pts: number[] = []
        for (let a = 0; a <= 128; a++) {
          const t = (a / 128) * Math.PI * 2
          pts.push(Math.cos(t) * cfg.r, 0, Math.sin(t) * cfg.r)
        }
        const g = new THREE.BufferGeometry()
        g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
        const ring = new THREE.Line(g, ringMat)
        ring.rotation.x = cfg.tilt
        rig.add(ring)
        rings.push(ring)
      })

      // ---- 星尘：满屏细小光点，给深底纵深，不占前景注意力 ----
      const DUST = 260
      const dustXYZ = new Float32Array(DUST * 3)
      for (let i = 0; i < DUST; i++) {
        dustXYZ[i * 3] = (Math.random() - 0.5) * 34
        dustXYZ[i * 3 + 1] = (Math.random() - 0.5) * 20
        dustXYZ[i * 3 + 2] = (Math.random() - 0.5) * 22 - 4
      }
      const dustGeo = new THREE.BufferGeometry()
      dustGeo.setAttribute('position', new THREE.BufferAttribute(dustXYZ, 3))
      const dustMat = new THREE.PointsMaterial({
        size: 0.05,
        color: 0x6ea8ff,
        transparent: true,
        opacity: 0.5,
        sizeAttenuation: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      })
      const dust = new THREE.Points(dustGeo, dustMat)
      scene.add(dust) // 挂 scene 不挂 rig：星尘不随主体转，只微微飘

      // ---- 交互：鼠标视差 ----
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

      const tmp = new THREE.Vector3()
      let spin = 0
      let t = 0
      const draw = () => {
        rig.rotation.y += (spin + mx * 0.22 - rig.rotation.y) * 0.045
        rig.rotation.x += (-my * 0.11 - rig.rotation.x) * 0.045
        paper.rotation.y += (0.36 + mx * 0.1 - paper.rotation.y) * 0.05

        // 数据流：每颗粒子在 from→to 之间循环推进，到头折回
        const sarr = streamGeo.attributes.position.array as Float32Array
        for (let i = 0; i < streams.length; i++) {
          const s = streams[i]
          const u = (t * 0.35 + s.phase) % 1
          tmp.lerpVectors(s.from, s.to, u)
          sarr[i * 3] = tmp.x
          sarr[i * 3 + 1] = tmp.y
          sarr[i * 3 + 2] = tmp.z
        }
        streamGeo.attributes.position.needsUpdate = true

        // 节点呼吸：整体亮度轻微起伏，像"在思考"
        nodeMat.opacity = 0.8 + Math.sin(t * 1.6) * 0.15
        rings.forEach((r, i) => (r.rotation.z += 0.0006 * (i ? -1 : 1)))
        dust.rotation.y += 0.0004

        renderer.render(scene, camera)
      }

      if (reduce) {
        spin = 0.35
        rig.rotation.y = 0.35
        draw()
        cleanups.push(() => renderer.dispose())
        return
      }

      draw() // 先同步画一帧

      let raf = 0
      let visible = true
      let last = performance.now()
      const tick = (now: number) => {
        raf = requestAnimationFrame(tick)
        if (!visible) return
        const dt = Math.min((now - last) / 1000, 0.05)
        last = now
        t += dt
        spin += 0.0012
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
        streamGeo.dispose()
        dustGeo.dispose()
        nodeMat.dispose()
        lineMat.dispose()
        streamMat.dispose()
        dustMat.dispose()
        ringMat.dispose()
        glow.dispose()
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
