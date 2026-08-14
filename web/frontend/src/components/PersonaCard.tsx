import { cn } from '@/lib/utils'
import { t, missingMarker } from '@/i18n/runtime'
import { getLocale } from '@/i18n/locale'
import { formatPercent } from '@/i18n/format'
import type { PlainMessageKey } from '@/i18n/keys.gen'
import type { Persona } from '@/lib/mock-data'
import { localizePersona } from '@/i18n/catalog'
import PersonaRadarChart from './PersonaRadarChart'
import PersonaAvatar from './PersonaAvatar'

type PersonaStatus = 'pending' | 'running' | 'completed' | 'failed'

interface PersonaCardProps {
  persona: Persona
  status?: PersonaStatus
  progress?: number
  primaryStance?: string
  confidence?: number
  topIssue?: string
  selected?: boolean
  compact?: boolean
  onClick?: () => void
}

const statusColors: Record<PersonaStatus, string> = {
  pending: 'bg-status-waiting',
  running: 'bg-status-running animate-pulse-glow',
  completed: 'bg-status-completed',
  failed: 'bg-status-failed',
}

/** 下面两张表存的是 **key 不是文案**：模块级常量存翻译结果的话，切换语言不会
 *  重新求值，卡片会一直停在打开页面时的那种语言（同 Layout.tsx 的 navItems）。 */
const statusLabelKeys: Record<PersonaStatus, PlainMessageKey> = {
  pending: 'enum.persona_status.pending',
  running: 'enum.persona_status.running',
  completed: 'enum.persona_status.completed',
  failed: 'enum.persona_status.failed',
}

const stanceColors: Record<string, string> = {
  advocate: 'text-brand-primary',
  neutral: 'text-severity-medium',
  skeptic: 'text-warm-orange',
  blocker: 'text-severity-critical',
}

const stanceLabelKeys: Record<string, PlainMessageKey> = {
  advocate: 'enum.primary_stance.advocate',
  neutral: 'enum.primary_stance.neutral',
  skeptic: 'enum.primary_stance.skeptic',
  blocker: 'enum.primary_stance.blocker',
}

/**
 * 立场标签。认不出来的取值**显式标记缺失**，不回落成后端原值。
 *
 * 原来写的是 `stanceLabels[primaryStance] ?? primaryStance`：后端加了第五档立场
 * （或改了拼写）时，卡片上会直接显示 "advocate" 这样的英文标识符，看起来像
 * 一个正常的标签，缺译因此隐身。契约 D8：缺译只能表现为 ⟦missing:…⟧。
 * 颜色仍然回落到中性色——**样式**没有"如实表达不知道"的表达方式，
 * 而且回落配色不会让用户误读成一个确定的立场。
 */
function stanceLabel(primaryStance: string): string {
  const key = stanceLabelKeys[primaryStance]
  if (key === undefined) return missingMarker(`enum.primary_stance.${primaryStance}`, getLocale())
  return t(key)
}

export default function PersonaCard({ persona, status, progress, primaryStance, confidence, topIssue, selected, compact, onClick }: PersonaCardProps) {
  // 名字与 archetype 同一次 localizePersona 调用取好：10.3 推翻早期裁决后，
  // display_name（罗马音译）是纯展示层字段，英文界面下换掉这里显示的名字；
  // persona.name 本身没变，仍是匹配 / 审计 / recruit_types 的唯一事实源。
  const localizedText = localizePersona(persona)
  return (
    <div
      onClick={onClick}
      className={cn(
        // h-full：在卡片网格里与同行卡片等高
        'h-full rounded-xl border p-4 hover-lift',
        'bg-bg-card hover:bg-bg-card-hover',
        selected ? 'border-brand-primary border-glow-green shadow-[0_0_20px_rgba(10,132,255,0.15)]' : 'border-border',
        onClick && 'cursor-pointer'
      )}
    >
      <div className="flex items-start gap-3">
        <PersonaAvatar personaId={persona.id} size={40} className="mt-0.5" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {status !== undefined && (
              <div className={cn('w-2 h-2 rounded-full shrink-0', statusColors[status])} />
            )}
            <h3 className="font-semibold text-text-primary truncate">{localizedText.name}</h3>
          </div>
          {/* archetype 是表述层、按 ui_lang 取。
              truncate 成单行：英文覆盖层常比中文长得多，任其自由折行会把卡片
              顶成不同高度，和同一排的兄弟卡片对不齐（h-full 只保证外层等高，
              不保证内容不把自己撑爆）。 */}
          <p className="text-xs text-text-secondary mb-2 truncate">{localizedText.archetype}</p>

          {status !== undefined && (
            <div className="flex items-center gap-2 text-xs text-text-muted mb-2">
              <span>{t(statusLabelKeys[status])}</span>
              {progress !== undefined && (
                <>
                  <span>·</span>
                  <div className="flex-1 h-1.5 bg-bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full bg-cyan rounded-full transition-all duration-500"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  {/* 进度条读数走 @/i18n/format：百分号的位置与小数点写法各语种不同。
                      style 里的 width 仍然是裸的 `${progress}%`——那是 CSS 长度，
                      不是给人读的文案，翻译它会直接把进度条画坏。 */}
                  <span className="font-mono">{formatPercent(progress / 100)}</span>
                </>
              )}
            </div>
          )}

          {primaryStance && (
            <div className="flex items-center gap-2 text-xs mt-1">
              <span className={cn('font-medium', stanceColors[primaryStance] ?? 'text-text-secondary')}>
                {stanceLabel(primaryStance)}
              </span>
              {confidence !== undefined && (
                <span className="font-mono text-text-muted">
                  {t('common.persona_card.confidence.value', { value: formatPercent(confidence) })}
                </span>
              )}
            </div>
          )}

          {topIssue && (
            <p className="text-xs text-text-secondary mt-1 truncate">{topIssue}</p>
          )}
        </div>

        {!compact && (
          <div className="shrink-0">
            <PersonaRadarChart data={persona.behavior_profile} size={120} />
          </div>
        )}
      </div>
    </div>
  )
}
