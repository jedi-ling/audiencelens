/**
 * 对话式入口 —— 真正的多轮聊天，不是"填一次表单"。
 *
 * 完整链路：
 *   用户发消息 → 把本轮之前的所有用户发言拼接起来 → POST /api/intent/parse
 *        → 置信度不够就追问，用户的回答会和之前的话拼在一起再解析一次
 *        → 足够自信后展示确认卡片 → 确认 → POST /api/v2/reviews
 *        → 跳到进度页，WS 推送实时进度
 *
 * 拼接而非维护真正的多轮对话状态，是因为 intent_service 本身是无状态的单次解析——
 * 拼接用户历史发言等价于给它更多上下文，不需要后端改造就能获得"越聊越准"的效果。
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { Send, Sparkles, Paperclip, X, Image as ImageIcon, AlertTriangle, Lightbulb, ChevronDown } from 'lucide-react'
import { api, ApiError } from '@/lib/apiClient'
import { useSessionStore } from '@/store/session-store'
import type { IntentResult, Material } from '@/lib/types'

const UPLOAD_ACCEPT = '.png,.jpg,.jpeg,.webp,.gif,.txt,.md,.json,.yaml,.yml'

interface ImageAttachment {
  id: string
  filename: string
  image_data: string
}

const EXAMPLES = [
  '帮我评审一下这个产品的定价页，用户会不会觉得贵',
  '这是我们的新手引导流程，看看用户会不会中途放弃',
  '这是我的创业项目申报表，帮我用投资人的眼光过一遍',
]

const TASK_LABELS: Record<string, string> = {
  steam_page_review: 'Steam 商店页评审',
  demo_first_play: 'Demo 首玩评审',
  concept_review: '概念评审',
  monetization_review: '付费设计评审',
  looking_for_party_post: '组队招募文案评审',
  update_announcement_review: '更新公告评审',
  devlog_review: '开发日志评审',
  kickstarter_review: '众筹页评审',
  localization_review: '本地化评审',
  discord_community_review: 'Discord 社区评审',
  product_feedback_review: '产品反馈评审',
  pricing_page_review: '定价页评审',
  onboarding_review: '新手引导评审',
  pitch_review: '创业项目评审',
}

type ChatMessageBase =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; kind: 'text'; text: string }
  | { id: string; role: 'assistant'; kind: 'clarify'; question: string; candidates: string[] }
  | { id: string; role: 'assistant'; kind: 'confirm'; intent: IntentResult }
  | { id: string; role: 'assistant'; kind: 'error'; text: string; needsKey?: boolean }

type ChatMessage = ChatMessageBase & { ts: number }

let seq = 0
function nextId(): string {
  seq += 1
  return `m${seq}`
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

/** 置信度 → 用户可理解的把握档位与配色 */
function confidenceLevel(confidence: number): { label: string; barClass: string } {
  if (confidence >= 0.8) return { label: '高', barClass: 'bg-neon-green' }
  if (confidence >= 0.6) return { label: '中', barClass: 'bg-cyan' }
  return { label: '偏低', barClass: 'bg-warm-orange' }
}

/** 助手身份头像 —— 让对话双方一眼可辨 */
function AssistantAvatar() {
  return (
    <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-neon-green/30 bg-neon-green/10">
      <Sparkles className="h-3.5 w-3.5 text-neon-green" strokeWidth={1.5} />
    </div>
  )
}

/** 等待反馈：三点跳动，替代静态"思考中…" */
function ThinkingIndicator() {
  return (
    <div className="flex items-start gap-2.5">
      <AssistantAvatar />
      <div className="flex items-center gap-1.5 rounded-xl border border-border bg-bg-secondary px-4 py-3.5">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-text-muted"
            style={{ animationDelay: `${delay}ms` }}
          />
        ))}
      </div>
    </div>
  )
}

export default function AskPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { config, bootstrap, canReview } = useSessionStore()

  const [messages, setMessages] = useState<ChatMessage[]>(() => [
    {
      id: nextId(),
      role: 'assistant',
      kind: 'text',
      text: '我是 AudienceLens 的评审助手。说说你想评审什么——一个页面、一份文案、一个产品概念都行，我会组一个多角度的用户评审团来看。',
      // 开场白的发出时间；惰性初始化保证只在挂载时取一次
      ts: Date.now(),
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [submittingId, setSubmittingId] = useState<string | null>(null)
  const [attachments, setAttachments] = useState<ImageAttachment[]>([])
  const [uploading, setUploading] = useState(false)
  const [showExamples, setShowExamples] = useState(true) // 首轮后自动收起，随时可再展开
  const [preview, setPreview] = useState<ImageAttachment | null>(null) // 附件放大预览
  const historyRef = useRef<string[]>([]) // 累积的用户发言，作为下一次解析的完整上下文
  const listRef = useRef<HTMLDivElement>(null) // 消息列表容器：滚动只发生在它内部，不能带动 window
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  // 从落地页 chip / CTA 带来的 ?q=... 预填输入框（不自动发送，让用户能改）
  useEffect(() => {
    const q = searchParams.get('q')
    if (q) {
      // 挂载后同步预填一次输入框是有意为之（来自落地页的 ?q=），只允许这一次
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setInput(q)
      // 用掉后清掉 query，避免刷新/后退时重复预填
      searchParams.delete('q')
      setSearchParams(searchParams, { replace: true })
    }
    // 只在挂载时消费一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    // 只滚动消息容器自身——scrollIntoView 会把 window 一起拽下去（页面比视口高出一个 footer）
    const el = listRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const appendMessage = (m: ChatMessageBase) => setMessages((prev) => [...prev, { ...m, ts: Date.now() }])

  const send = async (raw: string) => {
    const text = raw.trim()
    if (!text || busy) return
    setInput('')
    setShowExamples(false) // 开聊后收起示例，给对话让出空间
    appendMessage({ id: nextId(), role: 'user', text })
    historyRef.current = [...historyRef.current, text]
    setBusy(true)
    try {
      const combined = historyRef.current.join('\n')
      const intent = await api.parseIntent(combined)
      if (intent.needs_clarification) {
        appendMessage({
          id: nextId(),
          role: 'assistant',
          kind: 'clarify',
          question: intent.clarifying_question ?? '能再说得具体一点吗？',
          candidates: intent.candidates,
        })
      } else {
        appendMessage({ id: nextId(), role: 'assistant', kind: 'confirm', intent })
      }
    } catch (e) {
      appendMessage({
        id: nextId(),
        role: 'assistant',
        kind: 'error',
        text: e instanceof Error ? e.message : '解析失败，请再说一次',
      })
    } finally {
      setBusy(false)
    }
  }

  const MAX_ATTACHMENTS = 8 // data URI 全量驻留内存，不设上限的话几十张截图能把页面拖垮

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        try {
          if (attachments.length >= MAX_ATTACHMENTS) {
            appendMessage({
              id: nextId(),
              role: 'assistant',
              kind: 'error',
              text: `最多附带 ${MAX_ATTACHMENTS} 张图片——先移除几张再继续上传`,
            })
            break
          }
          const result = await api.upload(file)
          if (result.kind === 'image') {
            setAttachments((prev) => [
              ...prev,
              { id: nextId(), filename: result.filename, image_data: result.image_data },
            ])
          } else {
            // 文本类附件：抽取的文字直接并入输入框，走原有的意图解析文字通道
            setInput((prev) => (prev ? `${prev}\n\n${result.text}` : result.text))
          }
        } catch (e) {
          appendMessage({
            id: nextId(),
            role: 'assistant',
            kind: 'error',
            text: `「${file.name}」上传失败：${e instanceof Error ? e.message : '未知错误'}`,
          })
        }
      }
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id))
  }

  const pickCandidate = (candidate: string) => {
    // 用户点了候选任务类型，等价于告诉助手"就是这个"，直接推进到确认卡片
    void send(`就是${TASK_LABELS[candidate] ?? candidate}`)
  }

  const confirmAndCreate = async (msgId: string, intent: IntentResult) => {
    if (!intent.task_type) return
    // 全局防重：多张确认卡片共存时，任何一张在提交中都不允许再发——
    // 否则双击/连点会创建出两个评审
    if (submittingId !== null) return
    setSubmittingId(msgId)
    try {
      const artifactText = historyRef.current.join('\n')
      const materials: Material[] = [
        { type: 'text', text: intent.artifact_text || artifactText },
        ...attachments.map((a) => ({ type: 'image' as const, image_data: a.image_data, filename: a.filename })),
      ]
      const res = await api.createReview({
        task_type: intent.task_type,
        artifact: { title: artifactText.slice(0, 60), materials },
        mode: intent.mode,
        persona_pack: intent.persona_pack,
      })
      appendMessage({ id: nextId(), role: 'assistant', kind: 'text', text: '评审团已经开庭，带你去看实时进度…' })
      setAttachments([])
      navigate(`/review/${res.review_id}`)
    } catch (e) {
      if (e instanceof ApiError && e.needsApiKey) {
        appendMessage({ id: nextId(), role: 'assistant', kind: 'error', text: e.message, needsKey: true })
      } else {
        appendMessage({
          id: nextId(),
          role: 'assistant',
          kind: 'error',
          text: e instanceof Error ? e.message : '发起评审失败',
        })
      }
    } finally {
      setSubmittingId(null)
    }
  }

  const ready = canReview()

  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] max-w-3xl flex-col px-4 py-6">
      <header className="mb-4 flex items-center gap-2">
        <Sparkles className="h-5 w-5 text-neon-green" strokeWidth={1.5} />
        <div>
          <h1 className="text-lg font-semibold text-text-primary font-display">对话评审</h1>
          <p className="text-xs text-text-muted">说人话，剩下的交给评审团</p>
        </div>
      </header>

      {config && !ready && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-warm-orange/40 bg-warm-orange/10 p-3 text-sm shrink-0">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warm-orange" strokeWidth={2} />
          <div>
            <p className="font-medium text-text-primary">尚未配置 API Key</p>
            <p className="mt-1 text-text-secondary">
              评审必须使用真实模型——模拟数据没有评审价值。
              <button
                className="ml-1 text-neon-green underline underline-offset-2 hover:text-neon-green-dim"
                onClick={() => navigate('/settings')}
              >
                去设置页填写
              </button>
            </p>
          </div>
        </div>
      )}

      <div ref={listRef} className="flex-1 space-y-4 overflow-y-auto rounded-xl border border-border bg-bg-card/60 p-4">
        {messages.map((m) => (
          <ChatBubble
            key={m.id}
            message={m}
            busy={submittingId === m.id}
            onPickCandidate={pickCandidate}
            onConfirm={(intent) => void confirmAndCreate(m.id, intent)}
            onGoSettings={() => navigate('/settings')}
          />
        ))}
        {busy && <ThinkingIndicator />}
      </div>

      {/* 示例入口常驻：首轮后自动收起，随时可再展开 */}
      <div className="mt-3 shrink-0">
        <button
          className="flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary transition-colors"
          onClick={() => setShowExamples((v) => !v)}
          aria-expanded={showExamples}
        >
          <Lightbulb className="h-3.5 w-3.5" strokeWidth={1.5} />
          试试这些例子
          <ChevronDown
            className={`h-3.5 w-3.5 transition-transform ${showExamples ? 'rotate-180' : ''}`}
            strokeWidth={1.5}
          />
        </button>
        {showExamples && (
          <div className="mt-2 flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                className="rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary hover:border-neon-green/40 hover:text-text-primary transition-colors"
                onClick={() => void send(ex)}
              >
                {ex}
              </button>
            ))}
          </div>
        )}
      </div>

      {attachments.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2 shrink-0">
          {attachments.map((a) => (
            <div
              key={a.id}
              className="group relative flex items-center gap-1.5 rounded-lg border border-border bg-bg-card px-2 py-1.5 text-xs text-text-secondary"
            >
              <button
                className="flex items-center gap-1.5"
                onClick={() => setPreview(a)}
                title="点击放大预览"
              >
                <img src={a.image_data} alt={a.filename} className="h-8 w-8 rounded object-cover" />
                <span className="max-w-[8rem] truncate">{a.filename}</span>
              </button>
              <button
                className="ml-1 text-text-muted hover:text-severity-critical transition-colors"
                onClick={() => removeAttachment(a.id)}
                aria-label={`移除 ${a.filename}`}
              >
                <X className="h-3.5 w-3.5" strokeWidth={2} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="mt-3 flex items-end gap-2 rounded-xl border border-border bg-bg-card p-2 shrink-0 transition-opacity">
        <input
          ref={fileInputRef}
          type="file"
          accept={UPLOAD_ACCEPT}
          multiple
          className="hidden"
          onChange={(e) => void handleFiles(e.target.files)}
        />
        <button
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-text-muted hover:bg-bg-secondary hover:text-text-primary transition-colors disabled:opacity-50"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          aria-label="上传截图或文件"
          title="上传截图 / demo 图 / 文件（图片会作为多模态材料让模型直接看）"
        >
          {uploading ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-text-muted border-t-transparent" />
          ) : (
            <Paperclip className="h-4 w-4" strokeWidth={2} />
          )}
        </button>
        <textarea
          className="min-h-[44px] max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-text-primary placeholder-text-muted outline-none disabled:opacity-50"
          placeholder="说说你想评审什么…（Enter 发送，Shift+Enter 换行）"
          value={input}
          disabled={busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void send(input)
            }
          }}
        />
        <button
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-neon-green text-bg-primary hover:bg-neon-green-dim transition-colors disabled:opacity-50"
          onClick={() => void send(input)}
          disabled={busy || !input.trim()}
          aria-label="发送"
        >
          {busy ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-bg-primary border-t-transparent" />
          ) : (
            <Send className="h-4 w-4" strokeWidth={2} />
          )}
        </button>
      </div>
      {attachments.length > 0 && (
        <p className="mt-1.5 flex items-center gap-1 text-[11px] text-text-muted shrink-0">
          <ImageIcon className="h-3 w-3" strokeWidth={1.5} />
          {attachments.length} 张图片将随评审一起发送给支持视觉的模型
        </p>
      )}

      {/* 附件放大预览：点击遮罩或右上角关闭 */}
      {preview && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-bg-primary/80 p-6 backdrop-blur-sm"
          onClick={() => setPreview(null)}
        >
          <div className="relative max-h-full max-w-3xl" onClick={(e) => e.stopPropagation()}>
            <img
              src={preview.image_data}
              alt={preview.filename}
              className="max-h-[80vh] rounded-xl border border-border object-contain"
            />
            <p className="mt-2 text-center text-xs text-text-muted">{preview.filename}</p>
            <button
              className="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full border border-border bg-bg-card text-text-secondary hover:text-text-primary transition-colors"
              onClick={() => setPreview(null)}
              aria-label="关闭预览"
            >
              <X className="h-4 w-4" strokeWidth={2} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function ChatBubble({
  message,
  busy,
  onPickCandidate,
  onConfirm,
  onGoSettings,
}: {
  message: ChatMessage
  busy: boolean
  onPickCandidate: (candidate: string) => void
  onConfirm: (intent: IntentResult) => void
  onGoSettings: () => void
}) {
  const timeLabel = formatTime(message.ts)

  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="flex max-w-[75%] flex-col items-end">
          <div className="rounded-xl rounded-br-sm bg-neon-green px-4 py-2.5 text-sm leading-relaxed text-bg-primary whitespace-pre-wrap">
            {message.text}
          </div>
          <span className="mt-1 text-[10px] text-text-muted">{timeLabel}</span>
        </div>
      </div>
    )
  }

  if (message.kind === 'text') {
    return (
      <div className="flex items-start gap-2.5">
        <AssistantAvatar />
        <div className="flex max-w-[75%] flex-col">
          <div className="rounded-xl rounded-tl-sm border border-border bg-bg-secondary px-4 py-2.5 text-sm leading-relaxed text-text-primary">
            {message.text}
          </div>
          <span className="mt-1 text-[10px] text-text-muted">{timeLabel}</span>
        </div>
      </div>
    )
  }

  if (message.kind === 'error') {
    return (
      <div className="flex items-start gap-2.5">
        <AssistantAvatar />
        <div className="flex max-w-[75%] flex-col">
          <div className="rounded-xl rounded-tl-sm border border-severity-critical/40 bg-severity-critical/10 px-4 py-2.5 text-sm leading-relaxed text-text-primary">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-severity-critical" strokeWidth={2} />
              <div>
                {message.text}
                {message.needsKey && (
                  <button
                    className="ml-2 text-neon-green underline underline-offset-2 hover:text-neon-green-dim"
                    onClick={onGoSettings}
                  >
                    去填写 API Key
                  </button>
                )}
              </div>
            </div>
          </div>
          <span className="mt-1 text-[10px] text-text-muted">{timeLabel}</span>
        </div>
      </div>
    )
  }

  if (message.kind === 'clarify') {
    return (
      <div className="flex items-start gap-2.5">
        <AssistantAvatar />
        <div className="flex max-w-[80%] flex-col">
          <div className="rounded-xl rounded-tl-sm border border-border bg-bg-secondary px-4 py-3 text-sm">
            <p className="leading-relaxed text-text-primary">{message.question}</p>
            {message.candidates.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {message.candidates.map((c) => (
                  <button
                    key={c}
                    className="rounded-md border border-border bg-bg-card px-3.5 py-2 text-sm text-text-primary hover:border-neon-green/40 hover:bg-bg-card-hover transition-colors"
                    onClick={() => onPickCandidate(c)}
                  >
                    {TASK_LABELS[c] ?? c}
                  </button>
                ))}
              </div>
            )}
          </div>
          <span className="mt-1 text-[10px] text-text-muted">{timeLabel}</span>
        </div>
      </div>
    )
  }

  // confirm —— 转化关键节点：大标题 + 把握可视化 + 次要信息 chip 化
  const intent = message.intent
  const conf = confidenceLevel(intent.confidence)
  return (
    <div className="flex items-start gap-2.5">
      <AssistantAvatar />
      <div className="flex w-full max-w-[85%] flex-col">
        <div className="rounded-xl rounded-tl-sm border border-neon-green/25 bg-bg-secondary px-5 py-4 text-sm">
          <p className="text-xs text-text-muted">我明白了，你想做的是</p>
          <h3 className="mt-1 text-base font-semibold text-text-primary font-display">
            {TASK_LABELS[intent.task_type ?? ''] ?? intent.task_type}
          </h3>

          <div className="mt-2.5 flex flex-wrap gap-2">
            <span className="rounded-md border border-border bg-bg-card px-2.5 py-1 text-xs text-text-secondary">
              深度 · {intent.mode}
            </span>
            <span className="rounded-md border border-border bg-bg-card px-2.5 py-1 text-xs text-text-secondary">
              评审团 · {intent.persona_pack}
            </span>
          </div>

          <div className="mt-3.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-text-muted">匹配把握</span>
              <span className="font-medium text-text-secondary">
                {conf.label}（{(intent.confidence * 100).toFixed(0)}%）
              </span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-bg-card">
              <div
                className={`h-full rounded-full ${conf.barClass} transition-all`}
                style={{ width: `${Math.round(intent.confidence * 100)}%` }}
              />
            </div>
            {intent.method !== 'llm' && (
              <p className="mt-2 text-xs text-text-muted">
                未配置 API Key，本次为规则解析，任务类型可能判得不准——填 Key 后用模型解析会更靠谱。
              </p>
            )}
          </div>

          <button
            className="mt-4 w-full rounded-md bg-neon-green py-2.5 font-semibold text-bg-primary hover:bg-neon-green-dim transition-colors disabled:opacity-50"
            onClick={() => onConfirm(intent)}
            disabled={busy}
          >
            {busy ? '开庭中…' : '开庭评审 →'}
          </button>
        </div>
        <span className="mt-1 text-[10px] text-text-muted">{timeLabel}</span>
      </div>
    </div>
  )
}
