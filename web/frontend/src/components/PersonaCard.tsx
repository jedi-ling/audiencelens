import { cn } from '@/lib/utils'
import type { Persona } from '@/lib/mock-data'
import PersonaRadarChart from './PersonaRadarChart'

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

const statusLabels: Record<PersonaStatus, string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  failed: '失败',
}

const stanceColors: Record<string, string> = {
  advocate: 'text-brand-primary',
  neutral: 'text-severity-medium',
  skeptic: 'text-warm-orange',
  blocker: 'text-severity-critical',
}

const stanceLabels: Record<string, string> = {
  advocate: '支持',
  neutral: '中立',
  skeptic: '质疑',
  blocker: '反对',
}

export default function PersonaCard({ persona, status, progress, primaryStance, confidence, topIssue, selected, compact, onClick }: PersonaCardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        // h-full：在卡片网格里与同行卡片等高
        'h-full rounded-xl border-2 p-4 transition-all duration-200',
        'bg-bg-card hover:bg-bg-card-hover',
        selected ? 'border-brand-primary border-glow-green' : 'border-border',
        onClick && 'cursor-pointer'
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {status !== undefined && (
              <div className={cn('w-2 h-2 rounded-full shrink-0', statusColors[status])} />
            )}
            <h3 className="font-semibold text-text-primary truncate">{persona.name}</h3>
          </div>
          <p className="text-xs text-text-secondary mb-2">{persona.archetype}</p>

          {status !== undefined && (
            <div className="flex items-center gap-2 text-xs text-text-muted mb-2">
              <span>{statusLabels[status]}</span>
              {progress !== undefined && (
                <>
                  <span>·</span>
                  <div className="flex-1 h-1.5 bg-bg-secondary rounded-full overflow-hidden">
                    <div
                      className="h-full bg-cyan rounded-full transition-all duration-500"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <span className="font-mono">{progress}%</span>
                </>
              )}
            </div>
          )}

          {primaryStance && (
            <div className="flex items-center gap-2 text-xs mt-1">
              <span className={cn('font-medium', stanceColors[primaryStance] ?? 'text-text-secondary')}>
                {stanceLabels[primaryStance] ?? primaryStance}
              </span>
              {confidence !== undefined && (
                <span className="font-mono text-text-muted">
                  置信度 {(confidence * 100).toFixed(0)}%
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
