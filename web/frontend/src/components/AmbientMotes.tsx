/**
 * 环境浮尘 —— 纯 CSS 的轻量氛围粒子。
 *
 * 为什么不用 canvas：本仓库原来有个 ParticleConstellation.tsx（已删），
 * 它用 canvas + requestAnimationFrame 跑 80 个粒子并做 O(n²) 连线判定
 * ——每帧 3160 次距离计算，60fps 下每秒 19 万次，且无法尊重系统的
 * prefers-reduced-motion。氛围粒子不值得这个代价。
 *
 * 这里改成一组绝对定位的小圆点，只动 transform / opacity（GPU 合成，
 * 不触发 layout/paint），CSS 层面就能被 reduced-motion 关停（见 index.css .mote）。
 *
 * 用在哪：hero、空状态这类「没有内容要读」的区域。
 * 不要用在正文底下 —— 文字后面飘东西会持续偷走注意力，是在帮倒忙。
 */

/**
 * 固定的一组位置/时长，而不是 Math.random()。
 * 随机会导致每次 render 粒子瞬移（动画重置），也让视觉不可复现；
 * 手挑的分布还能避开正中间（hero 主标题所在处）。
 */
const MOTES = [
  { left: '8%', top: '22%', size: 3, dx: '32px', dy: '-46px', dur: '19s', delay: '0s' },
  { left: '17%', top: '68%', size: 2, dx: '-24px', dy: '-38px', dur: '23s', delay: '2.4s' },
  { left: '26%', top: '12%', size: 4, dx: '18px', dy: '52px', dur: '21s', delay: '5.1s' },
  { left: '34%', top: '82%', size: 2, dx: '40px', dy: '-30px', dur: '26s', delay: '1.2s' },
  { left: '43%', top: '34%', size: 3, dx: '-30px', dy: '44px', dur: '18s', delay: '7.3s' },
  { left: '58%', top: '18%', size: 2, dx: '26px', dy: '40px', dur: '24s', delay: '3.6s' },
  { left: '67%', top: '74%', size: 3, dx: '-36px', dy: '-34px', dur: '20s', delay: '6.2s' },
  { left: '76%', top: '28%', size: 4, dx: '22px', dy: '48px', dur: '27s', delay: '0.8s' },
  { left: '84%', top: '58%', size: 2, dx: '-28px', dy: '-42px', dur: '22s', delay: '4.5s' },
  { left: '91%', top: '15%', size: 3, dx: '34px', dy: '36px', dur: '25s', delay: '8.1s' },
  { left: '12%', top: '45%', size: 2, dx: '30px', dy: '-28px', dur: '28s', delay: '5.7s' },
  { left: '52%', top: '88%', size: 3, dx: '-20px', dy: '-50px', dur: '17s', delay: '2.9s' },
] as const

export default function AmbientMotes({ className = '' }: { className?: string }) {
  return (
    // aria-hidden：纯装饰，不该被读屏软件念出来
    <div
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 overflow-hidden ${className}`}
    >
      {MOTES.map((m, i) => (
        <span
          key={i}
          className="mote"
          style={{
            left: m.left,
            top: m.top,
            width: m.size,
            height: m.size,
            // CSS 自定义属性驱动 keyframes，省掉 12 份重复的 @keyframes
            ['--mote-dx' as string]: m.dx,
            ['--mote-dy' as string]: m.dy,
            ['--mote-dur' as string]: m.dur,
            ['--mote-delay' as string]: m.delay,
          }}
        />
      ))}
    </div>
  )
}
