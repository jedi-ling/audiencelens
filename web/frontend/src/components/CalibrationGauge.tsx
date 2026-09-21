/**
 * 校准指标仪表盘。
 *
 * 合格线必须由调用方按**该指标自己的**判定口径传进来（src/runner/calibration.py
 * 的 run_calibration_check：角色一致性 >= 0.8、视角覆盖度 >= 0.3）。
 * 这里原本写死「>=80% 绿 / >=60% 蓝 / >=40% 橙 / 否则红」，对角色一致性恰好对得上，
 * 对视角覆盖度就完全反了：0.35 是合格值，却被涂成红色 35%，页脚同时写着"校准通过"。
 * 一个指标的颜色和同一屏的结论互相打架，用户只会相信那个红色。
 *
 * passLine 不传时**不做好坏判断**，只用中性色：宁可不表态，也不能给一个没有事实
 * 依据的合格线涂上红绿。无幻觉率就是这种情况——overall_pass 根本没把它算进去。
 */
import { t } from '@/i18n/runtime'
import { formatPercent } from '@/i18n/format'

interface CalibrationGaugeProps {
  label: string
  /** 取不到就传 null/undefined。**不要**替它兜底成 0：0 会被画成一根满红的
   *  "这项指标烂透了"，而真相是这项指标根本没算出来。 */
  value: number | null | undefined
  max?: number
  /** 合格线，与 value 同量纲（不是百分比）。缺省表示该指标没有已定义的合格线 */
  passLine?: number
  /** 合格线的出处，显示给用户看，免得这条线本身又变成一个来路不明的数 */
  passLineNote?: string
}

// 深色主题：合格线颜色沿用深色语义 token（status-completed / severity-high / severity-critical），
// 弧线底色和缺省色沿用 border / text-muted——原来的 #e5e5ea 弧线在 #1c1c1e 卡片上亮得刺眼。
const COLOR_PASS = '#32d74b'
const COLOR_NEAR = '#ff9f0a'
const COLOR_FAIL = '#ff453a'
const COLOR_NEUTRAL = '#636366'
const COLOR_TRACK = '#38383a'

export default function CalibrationGauge({ label, value, max = 1, passLine, passLineNote }: CalibrationGaugeProps) {
  const missing = value === null || value === undefined || Number.isNaN(value)
  const percentage = missing ? 0 : (value / max) * 100
  const angle = (percentage / 100) * 180

  // 只分「达标 / 差得不多 / 差得远」三档，档位边界全部从 passLine 派生。
  // 「差得不多」取合格线的 80%：这是纯展示上的分档，不参与任何判定，
  // 所以不会凭空造出第二条"合格线"来。
  const color = (() => {
    if (missing || passLine === undefined) return COLOR_NEUTRAL
    if (value! >= passLine) return COLOR_PASS
    if (value! >= passLine * 0.8) return COLOR_NEAR
    return COLOR_FAIL
  })()

  // 合格线在弧上的位置：只有把线画出来，用户才看得懂 35% 为什么是绿的
  const passAngle = passLine === undefined ? null : Math.min(Math.max(passLine / max, 0), 1) * 180
  const passRad = passAngle === null ? 0 : (passAngle - 90) * (Math.PI / 180) - Math.PI

  return (
    <div
      className="flex flex-col items-center gap-2"
      role="img"
      // 读数拿不到时复用 missing.hint（"这项没算出来"），不在这里写死一个
      // 中文的"无数据"：英文界面上那个字面量会原样漏出去，而且它和脚注
      // 里那句话会变成对同一件事的两种说法。
      aria-label={t('common.calibration_gauge.gauge.aria', {
        label,
        value: missing ? t('common.calibration_gauge.missing.hint') : formatPercent(percentage / 100),
      })}
    >
      <svg width="140" height="80" viewBox="0 0 140 80" aria-hidden="true">
        <path
          d="M 10 75 A 60 60 0 0 1 130 75"
          fill="none"
          stroke="var(--color-border, #38383a)"
          strokeWidth="10"
          strokeLinecap="round"
        />
        <path
          d="M 10 75 A 60 60 0 0 1 130 75"
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${(angle / 180) * 188.5} 188.5`}
          style={{ filter: `drop-shadow(0 0 6px ${color}40)` }}
        />
        {passAngle !== null && (
          <line
            x1={70 + 52 * Math.cos(passRad)}
            y1={75 + 52 * Math.sin(passRad)}
            x2={70 + 68 * Math.cos(passRad)}
            y2={75 + 68 * Math.sin(passRad)}
            stroke="#8e8e93"
            strokeWidth="2"
            strokeLinecap="round"
          />
        )}
        <line
          x1="70"
          y1="75"
          x2={70 + 55 * Math.cos((angle - 90) * (Math.PI / 180) - Math.PI)}
          y2={75 + 55 * Math.sin((angle - 90) * (Math.PI / 180) - Math.PI)}
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 4px ${color}60)` }}
        />
        <circle cx="70" cy="75" r="4" fill={color} />
      </svg>
      <div className="text-center">
        <span className="font-display text-lg font-bold tabular-nums" style={{ color }}>
          {/* 百分比走 @/i18n/format：原来是 toFixed(0) + 写死的 '%'，
              百分号的位置与小数点写法各语种不同，那是 Intl 的事（契约 6.5）。 */}
          {missing ? t('common.calibration_gauge.readout.empty') : formatPercent(percentage / 100)}
        </span>
        <p className="text-xs text-text-secondary mt-0.5">{label}</p>
        <p className="text-[10px] text-text-muted mt-0.5">
          {missing
            ? t('common.calibration_gauge.missing.hint')
            : passLine === undefined
              ? t('common.calibration_gauge.no_pass_line.hint')
              : t('common.calibration_gauge.pass_line.value', { value: formatPercent(passLine / max) })}
        </p>
        {passLineNote && <p className="text-[10px] text-text-muted">{passLineNote}</p>}
      </div>
    </div>
  )
}
