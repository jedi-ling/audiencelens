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
import { Send, Sparkles, Paperclip, X, Image as ImageIcon } from 'lucide-react'
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

type ChatMessage =
  | { id: string; role: 'user'; text: string }
  | { id: string; role: 'assistant'; kind: 'text'; text: string }
  | { id: string; role: 'assistant'; kind: 'clarify'; question: string; candidates: string[] }
  | { id: string; role: 'assistant'; kind: 'confirm'; intent: IntentResult }
  | { id: string; role: 'assistant'; kind: 'error'; text: string; needsKey?: boolean }

let seq = 0
function nextId(): string {
  seq += 1
  return `m${seq}`
}

export default function AskPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { config, bootstrap, canReview } = useSessionStore()

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: nextId(),
      role: 'assistant',
      kind: 'text',
      text: '我是 AudienceLens 的评审助手。说说你想评审什么——一个页面、一份文案、一个产品概念都行，我会组一个多角度的用户评审团来看。',
    },
  ])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [submittingId, setSubmittingId] = useState<string | null>(null)
  const [attachments, setAttachments] = useState<ImageAttachment[]>([])
  const [uploading, setUploading] = useState(false)
  const historyRef = useRef<string[]>([]) // 累积的用户发言，作为下一次解析的完整上下文
  const bottomRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  // 从落地页 chip / CTA 带来的 ?q=... 预填输入框（不自动发送，让用户能改）
  useEffect(() => {
    const q = searchParams.get('q')
    if (q) {
      setInput(q)
      // 用掉后清掉 query，避免刷新/后退时重复预填
      searchParams.delete('q')
      setSearchParams(searchParams, { replace: true })
    }
    // 只在挂载时消费一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const appendMessage = (m: ChatMessage) => setMessages((prev) => [...prev, m])

  const send = async (raw: string) => {
    const text = raw.trim()
    if (!text || busy) return
    setInput('')
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
        <div className="mb-4 rounded-lg border border-warm-orange/40 bg-warm-orange/10 p-3 text-sm shrink-0">
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
      )}

      <div className="flex-1 space-y-3 overflow-y-auto rounded-xl border border-border bg-bg-card/60 p-4">
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
        {busy && (
          <div className="flex justify-start">
            <div className="rounded-xl border border-border bg-bg-secondary px-4 py-2.5 text-sm text-text-muted">
              思考中…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {messages.length <= 1 && (
        <div className="mt-3 flex flex-wrap gap-2 shrink-0">
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

      {attachments.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2 shrink-0">
          {attachments.map((a) => (
            <div
              key={a.id}
              className="group relative flex items-center gap-1.5 rounded-lg border border-border bg-bg-card px-2 py-1.5 text-xs text-text-secondary"
            >
              <img src={a.image_data} alt={a.filename} className="h-8 w-8 rounded object-cover" />
              <span className="max-w-[8rem] truncate">{a.filename}</span>
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

      <div className="mt-3 flex items-end gap-2 rounded-xl border border-border bg-bg-card p-2 shrink-0">
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
          className="min-h-[44px] max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-text-primary placeholder-text-muted outline-none"
          placeholder="说说你想评审什么…（Enter 发送，Shift+Enter 换行）"
          value={input}
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
          <Send className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>
      {attachments.length > 0 && (
        <p className="mt-1.5 flex items-center gap-1 text-[11px] text-text-muted shrink-0">
          <ImageIcon className="h-3 w-3" strokeWidth={1.5} />
          {attachments.length} 张图片将随评审一起发送给支持视觉的模型
        </p>
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
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-xl bg-neon-green/15 border border-neon-green/30 px-4 py-2.5 text-sm text-text-primary whitespace-pre-wrap">
          {message.text}
        </div>
      </div>
    )
  }

  if (message.kind === 'text') {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] rounded-xl border border-border bg-bg-secondary px-4 py-2.5 text-sm text-text-primary">
          {message.text}
        </div>
      </div>
    )
  }

  if (message.kind === 'error') {
    return (
      <div className="flex justify-start">
        <div className="max-w-[80%] rounded-xl border border-severity-critical/40 bg-severity-critical/10 px-4 py-2.5 text-sm text-text-primary">
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
    )
  }

  if (message.kind === 'clarify') {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] rounded-xl border border-border bg-bg-secondary px-4 py-3 text-sm">
          <p className="text-text-primary">{message.question}</p>
          {message.candidates.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {message.candidates.map((c) => (
                <button
                  key={c}
                  className="rounded-md border border-border bg-bg-card px-3 py-1.5 text-xs text-text-primary hover:border-neon-green/40 transition-colors"
                  onClick={() => onPickCandidate(c)}
                >
                  {TASK_LABELS[c] ?? c}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // confirm
  const intent = message.intent
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-xl border border-border bg-bg-secondary px-4 py-3 text-sm">
        <div className="mb-3 flex items-center gap-2 font-mono text-xs text-text-muted">
          <span>解析结果</span>
          <span className="rounded bg-bg-card px-2 py-0.5 text-text-secondary">
            {intent.method === 'llm' ? 'LLM 解析' : '规则解析（无 Key 降级）'}
          </span>
          <span>置信度 {(intent.confidence * 100).toFixed(0)}%</span>
        </div>
        <dl className="grid grid-cols-3 gap-3 text-xs">
          <div>
            <dt className="text-text-muted">任务类型</dt>
            <dd className="mt-1 font-medium text-text-primary">
              {TASK_LABELS[intent.task_type ?? ''] ?? intent.task_type}
            </dd>
          </div>
          <div>
            <dt className="text-text-muted">深度</dt>
            <dd className="mt-1 font-medium text-text-primary">{intent.mode}</dd>
          </div>
          <div>
            <dt className="text-text-muted">人格包</dt>
            <dd className="mt-1 font-medium text-text-primary">{intent.persona_pack}</dd>
          </div>
        </dl>
        <button
          className="mt-3 w-full rounded-md bg-neon-green py-2 font-semibold text-bg-primary hover:bg-neon-green-dim transition-colors disabled:opacity-50"
          onClick={() => onConfirm(intent)}
          disabled={busy}
        >
          {busy ? '开庭中…' : '开庭评审 →'}
        </button>
      </div>
    </div>
  )
}
