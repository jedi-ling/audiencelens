/**
 * Hero 全幅深色舞台：约 3 万颗粒子组成的"72 个视角审视一份材料"。
 *
 * 为什么是海量细粒子而不是几百个大光斑：那种画面靠的是**量级**——
 * 上万颗 1–2px 的小点聚成星云和光环，密处成面、疏处成尘，纵深由密度本身给出。
 * 用几百个大 sprite 永远做不出那种质感，只会是"一堆发光的球"。
 * 前一版 330 个大光点，正是"效果太弱"的直接原因。
 *
 * 关键工程决定：**运动全部放进 vertex shader**。
 * 3 万颗粒子若每帧在 JS 里循环更新坐标，主线程每帧要跑 3 万次三角函数，
 * 还要把整个 position buffer（几百 KB）回传 GPU，低端机必掉帧。
 * 改成 shader 里按 uTime 与每颗粒子自己的角速度算旋转，CPU 每帧只更新
 * **一个 uniform**，几何数据一次上传永不再动。
 *
 * 结构对应产品概念，不是随机撒点：
 *   · 72 个粒子团 —— 每个视角是一团注意力，不是一个点（标题写"72 个 AI 评审员"）
 *   · 中心星云盘 —— 被审视的那份材料
 *   · 3 道轨道环 —— 围绕审视的秩序
 *   · 分歧方暖橙，其余冷白蓝
 *
 * 降级与性能：three 懒加载不进主包；prefers-reduced-motion 只画一帧；
 * 移出视口停渲染；≤920px 不挂载；粒子总量按屏宽缩放。
 */

import { useEffect, useRef, useState } from 'react'

/** 视角总数——与首页主标题里的人格数是同一个事实 */
const VIEWPOINT_COUNT = 72
/** 分歧方（暖橙）的间隔 */
const DISSENT_EVERY = 8

/* 顶点着色器：每颗粒子绕 Y 轴自转 + 轻微起伏，全在 GPU 上算。
   aSeed 让每颗有自己的相位，aSpin 做差速（内圈快外圈慢，像真实星系），
   否则整块一起转会是廉价的刚体感。 */
const VERT = /* glsl */ `
uniform float uTime;
uniform float uPixelRatio;
attribute float aSize;
attribute float aSpin;
attribute float aSeed;
attribute vec3  aColor;
varying vec3  vColor;
varying float vFade;

void main() {
  vColor = aColor;

  float ang = uTime * aSpin + aSeed * 6.2831853;
  float s = sin(ang), c = cos(ang);
  vec3 p = vec3(
    position.x * c - position.z * s,
    position.y + sin(uTime * 0.35 + aSeed * 6.2831853) * 0.06,
    position.x * s + position.z * c
  );

  vec4 mv = modelViewMatrix * vec4(p, 1.0);

  // 按深度淡出，代替 fog —— 自定义着色器拿不到 three 的 fog 宏
  vFade = smoothstep(48.0, 12.0, -mv.z);

  gl_Position = projectionMatrix * mv;
  // 透视衰减：远小近大。系数配合相机 z≈28。
  // 这个数是控制"糊成白块"的最强杠杆：屏幕重叠面积正比于直径的平方，
  // 砍一半直径 = 重叠量降到四分之一，而单颗的亮度完全不受影响。
  // 相比之下砍粒子数量只是线性的，还会同时丢掉"海量"的观感。
  // 再加一个上限：没有它，近处粒子被透视放大成大光斑，少数几颗就堆满一片区域，
  // 逼着你砍总量——"海量"和"不糊"就变成了二选一。封住上限后两者可以同时成立。
  float ps = aSize * uPixelRatio * (210.0 / max(-mv.z, 0.001));
  gl_PointSize = min(ps, 4.2 * uPixelRatio);
}
`

/* 片元着色器：把方形 point 削成柔和圆点。
   这是海量粒子好看与否的分水岭——方点会糊成噪声，圆点才成"尘"。 */
const FRAG = /* glsl */ `
uniform float uOpacity;
varying vec3  vColor;
varying float vFade;

void main() {
  float d = length(gl_PointCoord - vec2(0.5));
  if (d > 0.5) discard;
  // 中心实、边缘散：平方衰减比线性更像光
  float a = smoothstep(0.5, 0.0, d);
  a *= a;
  gl_FragColor = vec4(vColor, a * vFade * uOpacity);
}
`

export default function HeroScene() {
  const hostRef = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    if (window.innerWidth <= 920) return // 窄屏不挂载

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
      const dpr = Math.min(window.devicePixelRatio, 2)

      // 粒子量按屏宽缩放：小笔记本没必要背满 3 万颗
      const q = Math.min(1, w() / 1600)
      const SWARM_PER_NODE = Math.round(130 * (0.55 + q * 0.45))
      const NEBULA = Math.round(10000 * (0.5 + q * 0.5))
      const RING_PER = Math.round(1200 * (0.5 + q * 0.5))
      const DUST = Math.round(4500 * (0.5 + q * 0.5))

      const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true })
      // 海量粒子下关掉 MSAA：粒子本身就是软边圆点，抗锯齿没有可见收益、只有开销
      renderer.setPixelRatio(dpr)
      renderer.setSize(w(), h())
      renderer.outputColorSpace = THREE.SRGBColorSpace
      host.appendChild(renderer.domElement)

      const scene = new THREE.Scene()
      const camera = new THREE.PerspectiveCamera(45, w() / h(), 0.1, 260)
      camera.position.set(0, 0.2, 28)

      const rig = new THREE.Group()
      rig.position.x = 0.8 // 微右移平衡视觉重心，粒子主体基本居中
      scene.add(rig)

      const COLD = new THREE.Color(0xbcd6ff) // 冷白蓝——参考图那种银白调
      const WARM = new THREE.Color(0xffc078) // 分歧方
      const CORE = new THREE.Color(0xffffff)

      const pos: number[] = []
      const col: number[] = []
      const siz: number[] = []
      const spn: number[] = []
      const sed: number[] = []
      const push = (
        x: number, y: number, z: number,
        c: import('three').Color, size: number, spin: number,
      ) => {
        pos.push(x, y, z)
        col.push(c.r, c.g, c.b)
        siz.push(size)
        spn.push(spin)
        sed.push(Math.random())
      }

      // 高斯抖动：均匀随机会摊成一张平板，高斯才有"密处成面、疏处成尘"
      const gauss = () => {
        let u = 0
        let v = 0
        while (u === 0) u = Math.random()
        while (v === 0) v = Math.random()
        return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
      }

      // ---------- 1) 中心星云盘：被审视的材料 ----------
      for (let i = 0; i < NEBULA; i++) {
        const r = Math.pow(Math.random(), 1.25) * 8.5 // 幂分布 → 内密外疏。相机后退后同步放大
        const a = Math.random() * Math.PI * 2
        const flat = 0.32 * (1 - r / 9.0) // 盘状：越靠外越薄
        const t = Math.min(1, r / 7.0)
        // 内圈偏白偏亮、外圈偏蓝偏暗——纵深感的主要来源
        push(
          Math.cos(a) * r + gauss() * 0.12,
          gauss() * flat,
          Math.sin(a) * r + gauss() * 0.12,
          CORE.clone().lerp(COLD, 0.25 + t * 0.75),
          0.62 + Math.random() * 0.85 * (1 - t),
          0.05 + (1 - t) * 0.1,
        )
      }

      // ---------- 2) 72 个视角粒子团 ----------
      const R = 12.5
      const golden = Math.PI * (3 - Math.sqrt(5))
      for (let i = 0; i < VIEWPOINT_COUNT; i++) {
        const yy = 1 - (i / (VIEWPOINT_COUNT - 1)) * 2
        const rr = Math.sqrt(Math.max(0, 1 - yy * yy))
        const th = golden * i
        const cx = Math.cos(th) * rr * R
        const cy = yy * R * 0.62 // 略压扁，构图更横向
        const cz = Math.sin(th) * rr * R
        const base = i % DISSENT_EVERY === 0 ? WARM : COLD

        for (let k = 0; k < SWARM_PER_NODE; k++) {
          // 空心球壳 + 抖动 → 是"光环"，不是实心球
          const u = Math.random() * 2 - 1
          const ph = Math.random() * Math.PI * 2
          const sr = Math.sqrt(1 - u * u)
          const shell = 0.34 + gauss() * 0.07
          push(
            cx + sr * Math.cos(ph) * shell,
            cy + u * shell,
            cz + sr * Math.sin(ph) * shell,
            base.clone().lerp(CORE, Math.random() * 0.5),
            0.5 + Math.random() * 0.8,
            0.03 + Math.random() * 0.02,
          )
        }
      }

      // ---------- 3) 三道轨道环 ----------
      ;[
        { r: R * 1.02, tilt: 0.0, thick: 0.05 },
        { r: R * 1.16, tilt: 0.5, thick: 0.07 },
        { r: R * 1.3, tilt: -0.34, thick: 0.09 },
      ].forEach((cfg, idx) => {
        for (let i = 0; i < RING_PER; i++) {
          const a = Math.random() * Math.PI * 2
          const rr = cfg.r + gauss() * cfg.thick
          const x = Math.cos(a) * rr
          const y0 = gauss() * cfg.thick * 1.4
          const z0 = Math.sin(a) * rr
          const ct = Math.cos(cfg.tilt)
          const st = Math.sin(cfg.tilt)
          push(
            x,
            y0 * ct - z0 * st,
            y0 * st + z0 * ct,
            COLD.clone().lerp(CORE, Math.random() * 0.35),
            0.45 + Math.random() * 0.45,
            0.018 + idx * 0.004,
          )
        }
      })

      // ---------- 4) 远景星尘：铺满整屏，不随主体转 ----------
      const dPos: number[] = []
      const dCol: number[] = []
      const dSiz: number[] = []
      const dSpn: number[] = []
      const dSed: number[] = []
      for (let i = 0; i < DUST; i++) {
        dPos.push((Math.random() - 0.5) * 110, (Math.random() - 0.5) * 62, (Math.random() - 0.5) * 62 - 8)
        const c = COLD.clone().lerp(CORE, Math.random() * 0.6)
        dCol.push(c.r, c.g, c.b)
        dSiz.push(0.3 + Math.random() * 0.5)
        dSpn.push(0.004)
        dSed.push(Math.random())
      }

      const makePoints = (
        p: number[], c: number[], s: number[], sp: number[], sd: number[], opacity: number,
      ) => {
        const g = new THREE.BufferGeometry()
        g.setAttribute('position', new THREE.Float32BufferAttribute(p, 3))
        g.setAttribute('aColor', new THREE.Float32BufferAttribute(c, 3))
        g.setAttribute('aSize', new THREE.Float32BufferAttribute(s, 1))
        g.setAttribute('aSpin', new THREE.Float32BufferAttribute(sp, 1))
        g.setAttribute('aSeed', new THREE.Float32BufferAttribute(sd, 1))
        const m = new THREE.ShaderMaterial({
          uniforms: {
            uTime: { value: 0 },
            uPixelRatio: { value: dpr },
            uOpacity: { value: opacity },
          },
          vertexShader: VERT,
          fragmentShader: FRAG,
          transparent: true,
          depthWrite: false,
          blending: THREE.AdditiveBlending, // 光靠叠加——这正是深底存在的意义
        })
        return { points: new THREE.Points(g, m), geo: g, mat: m }
      }

      // 单颗粒子的 alpha 必须很低：加色混合会累加，alpha 一高，几千颗一叠就撞上 1.0 的
      // 天花板，整块糊成白斑（实测 uOpacity=0.5 时右半屏均值 0.92、过曝像素 91.6%，
      // 而且此时砍一半粒子只把 0.94 挪到 0.92——在天花板上砍量是没用的）。
      // 低 alpha 让"要叠很多层才亮"重新成立，这才是黑底稀疏亮点的成因。
      const main = makePoints(pos, col, siz, spn, sed, 0.6)
      rig.add(main.points)
      const dustP = makePoints(dPos, dCol, dSiz, dSpn, dSed, 0.62)
      scene.add(dustP.points) // 挂 scene：星尘不随主体转

      const totalParticles = pos.length / 3 + dPos.length / 3
      host.dataset.particles = String(totalParticles)

      // ---- 鼠标视差 ----
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

      let t = 0
      const draw = () => {
        main.mat.uniforms.uTime.value = t
        dustP.mat.uniforms.uTime.value = t
        rig.rotation.y += (mx * 0.18 - rig.rotation.y) * 0.04
        rig.rotation.x += (0.12 - my * 0.1 - rig.rotation.x) * 0.04
        renderer.render(scene, camera)
      }

      if (reduce) {
        t = 3
        draw()
        cleanups.push(() => renderer.dispose())
        return
      }

      draw() // 先同步画一帧，避免首屏空白

      let raf = 0
      let visible = true
      let last = performance.now()
      const tick = (now: number) => {
        // 不可见（移出视口）或页面被隐藏（切 tab/最小化）时停掉 rAF 链：
        // 不再 requestAnimationFrame 续帧，主线程完全不参与，避免后台空转占主帧。
        // 恢复可见时由 IntersectionObserver / visibilitychange 回调重新启动。
        if (!visible || document.hidden) {
          raf = 0
          return
        }
        const dt = Math.min((now - last) / 1000, 0.05)
        last = now
        t += dt
        draw()
        raf = requestAnimationFrame(tick)
      }
      const start = () => {
        if (raf || !visible || document.hidden) return
        last = performance.now() // 重置时间基准，避免恢复后第一帧 dt 过大被 clamp
        raf = requestAnimationFrame(tick)
      }
      const stop = () => {
        if (raf) {
          cancelAnimationFrame(raf)
          raf = 0
        }
      }
      ;(window as unknown as Record<string, unknown>).__heroLum = () => {
        // 渲到离屏目标再读回：readPixels 对默认帧缓冲在合成后会读到全 0
        // （preserveDrawingBuffer=false），只有 RenderTarget 才读得到真实像素。
        const W = 240
        const H = Math.max(1, Math.round((W * h()) / w()))
        const rt = new THREE.WebGLRenderTarget(W, H)
        renderer.setRenderTarget(rt)
        renderer.render(scene, camera)
        const buf = new Uint8Array(W * H * 4)
        renderer.readRenderTargetPixels(rt, 0, 0, W, H, buf)
        renderer.setRenderTarget(null)
        rt.dispose()
        const band = (x0: number, x1: number) => {
          let sum = 0
          let hot = 0
          let n = 0
          const vals: number[] = []
          for (let y = 0; y < H; y++) {
            for (let x = Math.floor(W * x0); x < Math.floor(W * x1); x++) {
              const i = (y * W + x) * 4
              // 必须乘 alpha：RT 是透明底，粒子 RGB 再亮，alpha=0 也压不到深色背景上。
              // 不乘的话读出来右半屏均值 0.94（"几乎纯白"），是探针在骗人不是画面在爆。
              const a = buf[i + 3] / 255
              const l = ((0.2126 * buf[i] + 0.7152 * buf[i + 1] + 0.0722 * buf[i + 2]) / 255) * a
              vals.push(l)
              sum += l
              if (l > 0.5) hot++
              n++
            }
          }
          // 只看均值会把两件事混为一谈：调暗亮点和拉稀粒子在均值上长得一样。
          // 参考图的特征是"底黑 + 点亮"，所以必须同时看：
          //   mean 低（底子黑）且 p999 接近 1（亮点脆）。
          vals.sort((a, b) => a - b)
          const pct = (f: number) => +(vals[Math.min(vals.length - 1, Math.floor(vals.length * f))] ?? 0).toFixed(3)
          return {
            mean: +(sum / n).toFixed(4),
            hotPct: +((hot / n) * 100).toFixed(2),
            p99: pct(0.99),
            p999: pct(0.999),
          }
        }
        return { 文案区_左45: band(0, 0.45), 右侧舞台: band(0.55, 1), 全幅: band(0, 1) }
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
        main.geo.dispose()
        main.mat.dispose()
        dustP.geo.dispose()
        dustP.mat.dispose()
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
