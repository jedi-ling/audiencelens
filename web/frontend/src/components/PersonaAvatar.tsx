import { useState } from 'react'
import { cn } from '@/lib/utils'

interface PersonaAvatarProps {
  personaId: string
  size?: number
  className?: string
}

/**
 * 人格头像。路径由 id 确定性推出（/images/personas/<id>.webp），不经过后端——
 * 头像与语言无关，不需要 i18n 目录/overlay 那套机制。
 *
 * 素材是 ComfyUI（z_image_turbo）批量生成的写实头像照，2026-08 一次性产出 72 张，
 * 不是每次请求现生成。任何人格若日后改名/换代，头像需要跟着重新生成——
 * 这里不做「按 archetype 自动配图」之类的动态逻辑。
 *
 * 加载失败（该人格没有对应文件、文件名拼错）时不显示破图标——直接隐藏，
 * 卡片退回到没有头像之前的纯文字布局。这是刻意选择：一张裂图比没有图更抢眼、
 * 更容易被误读成"这个人格坏了"，而实际上只是缺一张装饰性头像。
 */
export default function PersonaAvatar({ personaId, size = 40, className }: PersonaAvatarProps) {
  const [failed, setFailed] = useState(false)
  if (failed) return null
  return (
    <img
      src={`/images/personas/${personaId}.webp`}
      alt=""
      aria-hidden="true"
      width={size}
      height={size}
      loading="lazy"
      onError={() => setFailed(true)}
      className={cn('rounded-full object-cover shrink-0 bg-bg-secondary', className)}
      style={{ width: size, height: size }}
    />
  )
}
