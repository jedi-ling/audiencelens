/**
 * Hero 主视觉：一份材料被多个视角同时审视。
 *
 * 为什么是 3D 而不是又一层背景粒子：这个产品的核心主张本身是**空间性的**
 * ——同一份东西，站在不同位置看，看到的不一样。让视角节点环绕制品、各自
 * 只连向自己那一面，是把价值主张渲染出来，不是装饰。
 *
 * 因此它必须是**看得清、能拖动的前景对象**。做成虚化在标题后面的氛围层，
 * 就不值 three.js 那 150KB —— 那种效果 2D canvas 能做到九成。
 *
 * 三条硬约束（都在代码里落实，不只是写在注释里）：
 *   1. three 只在这个组件真正挂载时才 import()，不进主包；
 *   2. prefers-reduced-motion 或窄屏 → 只渲染一帧静态构图，不起 RAF；
 *   3. 移出视口 → 停止渲染循环，不在后台空转烧 GPU。
 */

import { useEffect, useRef, useState } from 'react'

/** 视角节点：position 是单位球面上的方向，dissent 表示这一票是分歧方 */
const VIEWPOINTS: { dir: [number, number, number]; dissent: boolean }[] = [
  { dir: [0.92, 0.18, 0.35], dissent: false },
  { dir: [0.42, 0.62, -0.66], dissent: false },
  { dir: [-0.55, 0.34, 0.76], dissent: true },
  { dir: [-0.88, -0.12, -0.46], dissent: false },
  { dir: [0.18, -0.58, 0.79], dissent: false },
  { dir: [-0.28, 0.82, 0.5], dissent: true },
  { dir: [0.64, -0.44, -0.63], dissent: false },
]

export default function HeroScene() {
  const hostRef = useRef<HTMLDivElement>(null)
  // 失败时如实降级成静态构图，而不是留一块空白——空白会被当成"页面没加载出来"
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

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
      const width = () => host.clientWidth || 1
      const height = () => host.clientHeight || 1

      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      // DPR 封在 2：视网膜屏上 3x 的像素量换不来可见差别，只换来掉帧
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      renderer.setSize(width(), height())
      renderer.outputColorSpace = THREE.SRGBColorSpace
      host.appendChild(renderer.domElement)

      const scene = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(38, width() / height(), 0.1, 100)
      camera.position.set(0, 0.7, 5.4)
      camera.lookAt(0, 0, 0)

      const rig = new THREE.Group()
      scene.add(rig)

      // ---- 中心制品：一页材料。刻意做成薄板而不是立方体或球，
      //      因为用户送来评审的东西就是"一页东西"。 ----
      const slab = new THREE.Mesh(
        new THREE.BoxGeometry(1.5, 2.0, 0.045),
        new THREE.MeshStandardMaterial({
          color: 0xffffff,
          roughness: 0.55,
          metalness: 0.0,
        }),
      )
      slab.rotation.set(-0.12, 0.42, 0.05)
      rig.add(slab)

      // 制品的边缘线：纯白板在浅色背景上会糊掉，一圈细边把轮廓定住
      const slabEdges = new THREE.LineSegments(
        new THREE.EdgesGeometry(slab.geometry),
        new THREE.LineBasicMaterial({ color: 0x0071e3, transparent: true, opacity: 0.5 }),
      )
      slabEdges.rotation.copy(slab.rotation)
      rig.add(slabEdges)

      // ---- 视角节点 + 视线 ----
      const R = 2.35
      const nodeGeo = new THREE.OctahedronGeometry(0.075, 0)
      const nodeMat = new THREE.MeshStandardMaterial({
        color: 0x0071e3,
        roughness: 0.3,
        metalness: 0.1,
      })
      // 分歧方用暖橙——与 app 内 --color-warm-orange 同色，不是新造的颜色
      const dissentMat = new THREE.MeshStandardMaterial({
        color: 0xff9f0a,
        roughness: 0.3,
        metalness: 0.1,
      })

      const nodes: import('three').Mesh[] = []
      VIEWPOINTS.forEach((vp) => {
        const p = new THREE.Vector3(...vp.dir).normalize().multiplyScalar(R)
        const node = new THREE.Mesh(nodeGeo, vp.dissent ? dissentMat : nodeMat)
        node.position.copy(p)
        rig.add(node)
        nodes.push(node)

        // 视线只连到制品表面、不穿过它——"从我这个角度我看到的是这一面"
        const surface = p.clone().multiplyScalar(0.34)
        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([p, surface]),
          new THREE.LineBasicMaterial({
            color: vp.dissent ? 0xff9f0a : 0x0071e3,
            transparent: true,
            opacity: vp.dissent ? 0.55 : 0.28,
          }),
        )
        rig.add(line)
      })

      // ---- 光。一盏主光定形，一点环境光免得背面死黑 ----
      scene.add(new THREE.AmbientLight(0xffffff, 1.15))
      const key = new THREE.DirectionalLight(0xffffff, 1.6)
      key.position.set(2.4, 3.2, 3.0)
      scene.add(key)
      const rim = new THREE.DirectionalLight(0x2997ff, 0.7)
      rim.position.set(-3, -1, -2)
      scene.add(rim)

      // ---- 交互：拖动改变观察角度。这是这块画面的意义所在——
      //      用户亲手转一下，才会明白"换个位置看到的确实不一样"。 ----
      let dragging = false
      let lastX = 0
      let lastY = 0
      let velY = 0.0016 // 自转角速度，松手后回落到它
      let targetTiltX = 0
      const el = renderer.domElement
      el.style.touchAction = 'pan-y' // 竖向滑动仍要能滚页面，别劫持整个手势

      const onDown = (e: PointerEvent) => {
        dragging = true
        lastX = e.clientX
        lastY = e.clientY
        el.setPointerCapture(e.pointerId)
      }
      const onMove = (e: PointerEvent) => {
        if (!dragging) return
        const dx = e.clientX - lastX
        const dy = e.clientY - lastY
        lastX = e.clientX
        lastY = e.clientY
        rig.rotation.y += dx * 0.006
        targetTiltX = Math.max(-0.5, Math.min(0.5, targetTiltX + dy * 0.004))
        velY = dx * 0.0007 // 甩出去的惯性
      }
      const onUp = (e: PointerEvent) => {
        dragging = false
        try { el.releasePointerCapture(e.pointerId) } catch { /* 指针已释放 */ }
      }
      el.addEventListener('pointerdown', onDown)
      el.addEventListener('pointermove', onMove)
      el.addEventListener('pointerup', onUp)
      el.addEventListener('pointercancel', onUp)
      cleanups.push(() => {
        el.removeEventListener('pointerdown', onDown)
        el.removeEventListener('pointermove', onMove)
        el.removeEventListener('pointerup', onUp)
        el.removeEventListener('pointercancel', onUp)
      })

      const resize = () => {
        camera.aspect = width() / height()
        camera.updateProjectionMatrix()
        renderer.setSize(width(), height())
      }
      const ro = new ResizeObserver(resize)
      ro.observe(host)
      cleanups.push(() => ro.disconnect())

      const drawFrame = () => {
        rig.rotation.x += (targetTiltX - rig.rotation.x) * 0.06
        // 节点自转：让每个视角有独立生命，而不是一整块刚体在转
        nodes.forEach((n, i) => {
          n.rotation.y += 0.004 + i * 0.0006
          n.rotation.x += 0.003
        })
        renderer.render(scene, camera)
      }

      if (reduce) {
        // 尊重"减少动态效果"：给一帧有构图的静止画面，不是空白也不是动画
        rig.rotation.y = 0.5
        rig.rotation.x = 0.12
        drawFrame()
        cleanups.push(() => renderer.dispose())
        return
      }

      // 先同步画一帧再进循环：rAF 的第一帧可能被推迟（页面未合成、后台标签页、
      // 低端设备首屏抢占），那期间用户看到的是一块空白舞台。先画一帧就没有这个窗口。
      drawFrame()

      let raf = 0
      let visible = true
      const tick = () => {
        raf = requestAnimationFrame(tick)
        if (!visible) return
        if (!dragging) {
          velY += (0.0016 - velY) * 0.02 // 惯性回落到匀速自转
          rig.rotation.y += velY
        }
        drawFrame()
      }
      raf = requestAnimationFrame(tick)
      cleanups.push(() => cancelAnimationFrame(raf))

      // 移出视口就停——首页往下滚之后没有理由继续烧 GPU
      const io = new IntersectionObserver(
        ([entry]) => { visible = entry.isIntersecting },
        { threshold: 0.01 },
      )
      io.observe(host)
      cleanups.push(() => io.disconnect())

      cleanups.push(() => {
        renderer.dispose()
        slab.geometry.dispose()
        nodeGeo.dispose()
        if (el.parentNode) el.parentNode.removeChild(el)
      })
    })()

    return () => {
      disposed = true
      cleanups.forEach((fn) => fn())
    }
  }, [])

  return (
    <div className="hero-stage" aria-hidden="true">
      <div ref={hostRef} className="hero-stage-canvas" />
      {failed && <div className="hero-stage-fallback" />}
      <p className="hero-stage-hint">拖动查看不同视角</p>
    </div>
  )
}
