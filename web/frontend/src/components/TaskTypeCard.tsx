import { cn } from '@/lib/utils'
import type { TaskType } from '@/lib/mock-data'

interface TaskTypeCardProps {
  taskType: TaskType
  selected: boolean
  onClick: () => void
}

export default function TaskTypeCard({ taskType, selected, onClick }: TaskTypeCardProps) {
  const Icon = taskType.IconComponent

  return (
    <button
      onClick={onClick}
      className={cn(
        'flex flex-col items-center gap-3 rounded-xl border-2 p-5 transition-all duration-200 cursor-pointer',
        'bg-bg-card hover:bg-bg-card-hover',
        selected
          ? 'border-brand-primary border-glow-green'
          : 'border-border hover:border-border-hover hover:shadow-[0_8px_24px_rgba(0,0,0,0.08)]'
      )}
    >
      <div className={cn(
        'w-10 h-10 flex items-center justify-center rounded-lg transition-colors',
        selected ? 'bg-brand-primary/15' : 'bg-bg-secondary/50'
      )}>
        <Icon
          className={cn(
            'w-6 h-6 transition-colors',
            selected ? 'text-brand-primary' : 'text-text-secondary'
          )}
          strokeWidth={1.25}
        />
      </div>
      <span className={cn(
        'font-medium text-sm',
        selected ? 'text-brand-primary' : 'text-text-primary'
      )}>
        {taskType.name}
      </span>
      <span className="text-xs text-text-secondary text-center leading-relaxed">
        {taskType.description}
      </span>
    </button>
  )
}
