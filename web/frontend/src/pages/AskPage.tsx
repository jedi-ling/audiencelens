/**
 * 对话式入口 —— 真正的多轮聊天，不是"填一次表单"。
 *
 * 完整链路：
 *   用户发消息 → 把本轮之前的所有用户发言拼接起来 → POST /api/intent/parse
 *        → 置信度不够就追问，用户的回答会和之前的话拼在一起再解析一次
 *        → 足够自信后展示确认卡片 → 确认 → POST /api/v2/reviews
 *        → 评审卡片直接嵌进同一个对话（WS 推进度），不跳走——
 *          评审跑着的时候你还能继续聊，跑完了报告摘要也在这条对话里冒出来。
 *
 * 拼接而非维护真正的多轮对话状态，是因为 intent_service 本身是无状态的单次解析——
 * 拼接用户历史发言等价于给它更多上下文，不需要后端改造就能获得"越聊越准"的效果。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { Send, Sparkles, Paperclip, X, Image as ImageIcon, AlertTriangle, Lightbulb, ChevronDown, PanelLeftClose, PanelLeftOpen, Plus, Loader2, Trash2, Inbox, FolderOpen, Zap, Target, Search, ArrowRight, FileWarning, Coins, LogIn } from 'lucide-react'
import { cn } from '@/lib/utils'
import AmbientMotes from '@/components/AmbientMotes'
import { api, ApiError } from '@/lib/apiClient'
import { fetchReviewsAll, fetchReview, deleteReview, fetchPersonas } from '@/lib/api'
import { connectReviewSocket } from '@/lib/ws'
import type { WsStatus } from '@/lib/ws'
import { useSessionStore } from '@/store/session-store'
import { TASK_TYPES, SKILLS } from '@/lib/mock-data'
import type { ConversationSummary, IntentResult, Material, ReviewDetail, WsEvent } from '@/lib/types'
import type { Review, ReviewListItem } from '@/lib/mock-data'

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

const SKILL_LABELS: Record<string, string> = {
  red_team_audience: '红队受众',
  audience_panel: '受众面板',
}

type ChatMessageBase =
  | { id: string; role: 'user'; text: string; images?: string[] }
  | { id: string; role: 'assistant'; kind: 'text'; text: string; isGated?: boolean; fullLength?: number }
  | { id: string; role: 'assistant'; kind: 'clarify'; question: string; candidates: string[] }
  | { id: string; role: 'assistant'; kind: 'confirm'; intent: IntentResult }
  | { id: string; role: 'assistant'; kind: 'error'; text: string; needsKey?: boolean }
  | { id: string; role: 'assistant'; kind: 'review'; reviewId: string }

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
  if (confidence >= 0.8) return { label: '高', barClass: 'bg-brand-primary' }
  if (confidence >= 0.6) return { label: '中', barClass: 'bg-cyan' }
  return { label: '偏低', barClass: 'bg-warm-orange' }
}

/** 助手身份头像 —— 蓝色渐变徽记，让对话双方一眼可辨 */
function AssistantAvatar() {
  return (
    <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-primary shadow-[0_2px_8px_rgba(0,113,227,0.35)]">
      <Sparkles className="h-3.5 w-3.5 text-white" strokeWidth={1.5} />
    </div>
  )
}

/** 等待反馈：三点跳动（金色、1.4s 阻尼节奏），替代静态"思考中…" */
function ThinkingIndicator() {
  return (
    <div className="flex items-start gap-2.5 animate-message-in">
      <AssistantAvatar />
      <div className="flex items-center gap-1.5 rounded-xl rounded-tl-sm border border-border border-l-[3px] border-l-brand-primary/40 bg-bg-secondary px-4 py-3.5">
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand-primary/80 [animation-duration:1.4s]"
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
      text: '你好，说说你想评审什么——一个页面、一份文案、一个产品概念都可以。',
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
  // 累积"这轮对话里发过的所有图"，跨消息保留——用户可能先发一张图被追问，
  // answer 几句之后才凑齐 confirm 卡片，不能因为中途某条消息"发送"了
  // 就把图丢了：真正消费图片、清空这个累积区的时机是评审真的建出来那一刻。
  const sessionImagesRef = useRef<ImageAttachment[]>([])
  // 当前对话在服务端的 id。惰性创建：用户只是打开页面看看、一个字没发时
  // 不该在库里留下空对话。第一条消息落库时才真正建。
  const conversationIdRef = useRef<string | null>(null)
  // 建对话的在途 Promise。没有它的话，用户快速连发两条消息会并发触发两次
  // createConversation，第二条消息落进一段全新的空对话里，聊天记录被劈成两半。
  const creatingConvRef = useRef<Promise<string | null> | null>(null)
  const listRef = useRef<HTMLDivElement>(null) // 消息列表容器：滚动只发生在它内部，不能带动 window
  const fileInputRef = useRef<HTMLInputElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  /** 输入框随内容增高。配合 rows=1 用——rows=1 才能让单行文字与两侧 h-9 按钮对齐，
   *  但单行装不下长文，所以这里补上增高。上限交给 CSS 的 max-h-40，超了内部滚动。
   *  先置 auto 再读 scrollHeight 是必须的：不清空的话 scrollHeight 永远不小于当前
   *  height，删字时框只会一直变高、再也缩不回去。 */
  const autoGrow = (el: HTMLTextAreaElement) => {
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  // 高度跟随 input 的**任何**变化，不只是清空。
  //
  // 这里原先只处理 input === ''，于是所有**程序化**赋值都不长高：autoGrow 挂在
  // onChange 上，而 setInput 不派发 input 事件。落地页 CTA 的 /ask?q=... 预填
  // 就落在这条路上——实测 86 字中文时框停在 36px、内容需要 56px，用户从首页
  // 点进来看到的是一段被砍头的自己的话。附件抽取文本并入输入框同理。
  //
  // 空串时清掉内联高度而不是算一次：空 textarea 的 scrollHeight 会被浏览器
  // 按内容撑到上一次的残留值，直接清掉交给 CSS 的 min-h 更稳。
  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    if (input === '') el.style.height = ''
    else autoGrow(el)
  }, [input])

  // 窗口尺寸变了要重算：高度是按当时的宽度算出来的像素值，钉在内联样式上。
  // 拉窄窗口后同样的文字需要更多行，而内联高度纹丝不动——实测 192 字中文在
  // 1280 宽下是 96px，拉到 700 宽时实际需要 456px，只露出约 4 行，且因为没到
  // max-height，视觉上完全不像"该滚动"。要等用户下一次敲键盘才自愈。
  // 移动端横竖屏切换、拖窗口、开合侧栏都会触发。
  useEffect(() => {
    const onResize = () => {
      const el = inputRef.current
      if (el && el.value !== '') autoGrow(el)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // 输入框工具栏：手动钉住技能/任务类型，绕开"靠 AI 从大白话里猜"——
  // 钉住后覆盖 intent 解析结果，直到用户自己摘掉或新建对话。
  const [pinnedSkill, setPinnedSkill] = useState<{ type: string; name: string } | null>(null)
  // 高级技能剩余免费次数。null 值 = 该技能不受限（BYOK / 匿名 / 机制关闭），
  // 这时**不显示任何数字**——给 BYOK 用户看一个根本不适用于他的"剩余 3 次"，
  // 比不显示更糟。
  const [skillQuota, setSkillQuota] = useState<Record<string, number | null>>({})
  useEffect(() => {
    api.skillQuota()
      .then((q) => setSkillQuota(q.skills))
      .catch(() => setSkillQuota({}))  // 拿不到就不显示，不阻断选技能
  }, [])
  const [pinnedTaskType, setPinnedTaskType] = useState<{ id: string; name: string } | null>(null)
  const [pinnedProject, setPinnedProject] = useState<string | null>(null)
  // 报告出来后的追问——钉在同一个对话里，不弹独立窗口：钉住后普通发送
  // 就路由去跟这条评审（或某个具体人格）聊，而不是走意图解析开新评审。
  const [activeChatContext, setActiveChatContext] = useState<{
    reviewId: string
    personaId: string | null
    label: string
  } | null>(null)
  const [skillPickerOpen, setSkillPickerOpen] = useState(false)
  const [typePickerOpen, setTypePickerOpen] = useState(false)
  const [projectPickerOpen, setProjectPickerOpen] = useState(false)
  const [typeSearch, setTypeSearch] = useState('')
  const [newProjectName, setNewProjectName] = useState('')
  const [dragging, setDragging] = useState(false) // 拖拽文件悬停在聊天区上方时的视觉反馈

  // 左侧历史侧栏——桌面端默认展开，让用户不用跳出对话页就能回看/切换之前的评审
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [reviewHistory, setReviewHistory] = useState<ReviewListItem[] | null>(null)
  // 还没产出评审的对话。此前它们在侧栏里**完全不可见**——侧栏读的是评审列表，
  // 一条评审都还没建的对话就不存在于任何列表里，关掉页面等于永久消失。
  const [draftConvs, setDraftConvs] = useState<ConversationSummary[]>([])
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  // 正在等二次确认的那条（页面内确认，不用 window.confirm，理由见 askDeleteHistory）
  const [confirmingId, setConfirmingId] = useState<string | null>(null)
  // 后端说这个列表要登录才有内容（多租户实例上的未登录访客）。
  // 不加这个标记的话，用户看到的就是"历史莫名其妙空了"。
  const [historyRequiresLogin, setHistoryRequiresLogin] = useState(false)

  // 角色 id → 展示名（"呼叫角色"确认卡片用）；加载失败就退回显示 id，不阻断
  const [personaNames, setPersonaNames] = useState<Record<string, string>>({})

  useEffect(() => {
    let cancelled = false
    fetchPersonas()
      .then((list) => {
        if (cancelled) return
        const map: Record<string, string> = {}
        for (const p of list) map[p.id] = p.archetype || p.name
        setPersonaNames(map)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const { items, requiresLogin } = await fetchReviewsAll()
      setReviewHistory(items)
      setHistoryRequiresLogin(requiresLogin)
      setHistoryError(null)
      // 只列还没产出评审的对话：已经产出评审的那些，下面的评审历史里
      // 已经有一条了，两边都列会变成同一段对话出现两次。
      try {
        const { conversations } = await api.listConversations()
        setDraftConvs(conversations.filter((c) => !c.review_id))
      } catch {
        // 对话列表拉不到不该让评审历史也跟着空掉——两者是独立的失败面
      }
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : '加载失败')
    }
  }, [])

  useEffect(() => {
    void bootstrap()
    void loadHistory()
  }, [bootstrap, loadHistory])

  const startNewConversation = () => {
    historyRef.current = []
    sessionImagesRef.current = []
    // 断开与上一段对话的关联，否则新对话的消息会继续追加到旧对话里
    conversationIdRef.current = null
    creatingConvRef.current = null
    setAttachments([])
    setInput('')
    setShowExamples(true)
    setMessages([
      {
        id: nextId(),
        role: 'assistant',
        kind: 'text',
        text: '你好，说说你想评审什么——一个页面、一份文案、一个产品概念都可以。',
        ts: Date.now(),
      },
    ])
    setPinnedSkill(null)
    setPinnedTaskType(null)
    setPinnedProject(null)
    setActiveChatContext(null)
    searchParams.delete('review')
    searchParams.delete('c')
    setSearchParams(searchParams, { replace: true })
  }

  /** 点历史侧栏一条评审——不跳走、不弹窗，而是把这条评审"当年"对应的对话
   * 还原回主聊天区：用户原话重新变成一条用户气泡，评审结果还是那张 AI
   * 卡片（跟刚创建时一模一样，同一个 useReviewStatus，已完成的会立刻
   * 显示摘要，没跑完的会接着推进度）——没有持久化过完整对话记录，
   * 这是从 Review 自身数据能还原出的最接近"回到当时那个对话"的版本。 */
  const openReviewConversation = (r: Review) => {
    const bundle = r.artifact_bundle as { materials?: { type: string; text?: string }[] } | undefined
    const userText =
      bundle?.materials?.find((m) => m.type === 'text' && m.text)?.text ||
      r.target_title ||
      TASK_TYPES.find((t) => t.id === r.task_type)?.name ||
      '（历史评审）'
    historyRef.current = [userText]
    sessionImagesRef.current = []
    setAttachments([])
    setInput('')
    setShowExamples(false)
    setPinnedSkill(null)
    setPinnedTaskType(null)
    setPinnedProject(null)
    setMessages([
      { id: nextId(), role: 'user', text: userText, ts: Date.now() },
      { id: nextId(), role: 'assistant', kind: 'review', reviewId: r.id, ts: Date.now() },
    ])
    setSearchParams({ review: r.id }, { replace: true })

    // 追问的问答此前只存了数据库、从没在重新打开对话时重放——用户刷新页面
    // 或换个对话再回来，明明数据库里还在的追问记录在界面上却像是"从没问过"。
    // 这里把"跟评审团整体聊"的 thread（persona_id=null）拉回来接在评审卡片后面；
    // 具体人格的 thread 只有匿名用户看不到 persona_id（体验版报告裁掉了），
    // 登录用户能拿到真实 persona_id 就一并拉。
    if (r.status !== 'completed') return
    const restoreThread = async (personaId: string | null) => {
      try {
        const { messages: history } = await api.getReviewChat(r.id, personaId)
        return history.map((m): ChatMessage => {
          const ts = m.created_at ? new Date(m.created_at).getTime() : Date.now()
          if (m.role === 'user') {
            return { id: nextId(), role: 'user', text: m.content, ts }
          }
          return {
            id: nextId(),
            role: 'assistant',
            kind: 'text',
            text: m.content,
            isGated: m.is_gated,
            fullLength: m.full_length ?? undefined,
            ts,
          }
        })
      } catch {
        return []
      }
    }
    const report = r.report_json as { persona_notes?: Array<{ persona_id?: string }> } | null
    const personaIds = (report?.persona_notes ?? [])
      .map((n) => n.persona_id)
      .filter((id): id is string => !!id)

    void Promise.all([restoreThread(null), ...personaIds.map((pid) => restoreThread(pid))]).then(
      (threads) => {
        const restored = threads.flat().sort((a, b) => a.ts - b.ts)
        if (restored.length === 0) return
        setMessages((prev) => [...prev, ...restored])
      },
    )
  }

  /** 点垃圾桶：只进入"待确认"状态，不真删。
   *
   * 二次确认曾经用 window.confirm，实测不可靠：Chrome 在同一页面连弹几次后会给出
   * "阻止此页面创建更多对话框"的勾选框，用户勾上之后 confirm() 直接静默返回 false，
   * 于是点删除永远没反应、也没有任何报错——表现就是"删不掉"。某些内嵌 WebView
   * 也会整体屏蔽这类对话框。所以确认必须做在页面内，不依赖浏览器弹窗。
   */
  const askDeleteHistory = (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    e.stopPropagation()
    setHistoryError(null)
    setConfirmingId((prev) => (prev === id ? null : id))
  }

  /** 确认后真正删除。
   *
   * 失败必须看得见：以前失败只写进 historyError，而 historyError 从来不清，
   * 一次失败会一直挂着、下一次成功也不消失。现在开始前先清、失败写明原因。
   */
  const handleDeleteHistory = async (e: React.MouseEvent, id: string) => {
    e.preventDefault()
    e.stopPropagation()
    setConfirmingId(null)
    setDeletingId(id)
    setHistoryError(null)
    try {
      await deleteReview(id)
      setReviewHistory((prev) => (prev ? prev.filter((r) => r.id !== id) : prev))
      // 删掉的正是当前对话区展示的那条评审——继续停在一条已经不存在的评审上
      // 是错的（卡片会去拉一个 404 的详情），直接回到新对话。
      if (searchParams.get('review') === id) startNewConversation()
    } catch (err) {
      setHistoryError(
        err instanceof Error ? `删除失败：${err.message}` : '删除失败，请检查网络后重试',
      )
    } finally {
      setDeletingId(null)
    }
  }

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

  // 刷新页面（F5）不该把正在聊的对话打回开场白——confirmAndCreate/
  // openReviewConversation 都会把当前评审 id 写进 URL（?review=xxx），
  // 挂载时如果 URL 上带着它，就直接照着这个 id 把对话还原回来。
  useEffect(() => {
    const convId = searchParams.get('c')
    const reviewId = searchParams.get('review')
    if (!convId && !reviewId) return
    let cancelled = false

    // ?c= 优先：它是**真实存下来的**对话记录。
    // ?review= 那条路走的是 openReviewConversation，从 artifact_bundle 反推出
    // 一条用户气泡——在没有对话持久化之前那是唯一能做的近似，但它拿不回
    // 评审创建前的多轮澄清，时间戳也只能填 Date.now()。现在有真记录了，
    // 就不该再用近似值覆盖它。?review= 仍然保留：老链接和分享出去的
    // 评审地址得继续能打开。
    if (convId) {
      void api
        .getConversation(convId)
        .then((conv) => {
          if (cancelled) return
          conversationIdRef.current = conv.id
          const restored: ChatMessage[] = conv.messages.map((m) => {
            const ts = m.created_at ? new Date(m.created_at).getTime() : Date.now()
            const meta = (m.meta || {}) as { kind?: string; reviewId?: string | null }
            if (m.role === 'user') {
              return { id: nextId(), role: 'user', text: m.content, ts }
            }
            // 评审卡片按原样还原成卡片，而不是退化成一句文字
            if (meta.kind === 'review' && meta.reviewId) {
              return { id: nextId(), role: 'assistant', kind: 'review', reviewId: meta.reviewId, ts }
            }
            return { id: nextId(), role: 'assistant', kind: 'text', text: m.content, ts }
          })
          if (restored.length) {
            setMessages(restored)
            setShowExamples(false)
            // 重建解析上下文，否则接着说话时系统会当成全新一轮，
            // 把之前澄清过的信息全忘掉、再问一遍
            historyRef.current = conv.messages.filter((m) => m.role === 'user').map((m) => m.content)
          }
        })
        .catch(() => {
          // 对话被删了或不属于当前身份——静默回到开场白
        })
      return () => {
        cancelled = true
      }
    }

    void fetchReview(reviewId as string)
      .then((r) => {
        if (!cancelled) openReviewConversation(r)
      })
      .catch(() => {
        // 评审已被删除或不存在——静默回到开场白，不用报错打断使用
      })
    return () => {
      cancelled = true
    }
    // 只在挂载时消费一次
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    // 只滚动消息容器自身——scrollIntoView 会把 window 一起拽下去（页面比视口高出一个 footer）
    const el = listRef.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages])

  /** 拿到（必要时创建）当前对话的服务端 id。并发安全见 creatingConvRef 的注释。 */
  const ensureConversation = async (): Promise<string | null> => {
    if (conversationIdRef.current) return conversationIdRef.current
    if (creatingConvRef.current) return creatingConvRef.current
    const p = api
      .createConversation()
      .then((c) => {
        conversationIdRef.current = c.id
        // 写进 URL：刷新后靠它把对话捞回来。用 replace 不留历史记录，
        // 否则用户按后退键会在同一段对话的不同阶段之间来回跳。
        const next = new URLSearchParams(searchParams)
        next.set('c', c.id)
        setSearchParams(next, { replace: true })
        return c.id
      })
      .catch(() => null)
      .finally(() => {
        creatingConvRef.current = null
      })
    creatingConvRef.current = p
    return p
  }

  /** 把一条消息落库。**故意不 await、失败也不打断用户**：
   *  持久化失败时正确的行为是"这次没存上"，而不是"你这句话发不出去"。
   *  真正的可靠性来自服务端，前端在这里挡住失败只会让人白打一遍字。 */
  /** 把一条消息落库。**故意不 await、失败也不打断用户**：
   *  持久化失败时正确的行为是"这次没存上"，而不是"你这句话发不出去"。
   *  前端在这里挡住失败只会让人白打一遍字。 */
  const persistMessage = (m: ChatMessageBase) => {
    let role: 'user' | 'assistant' = 'assistant'
    let content = ''
    let meta: Record<string, unknown> | null = null

    if (m.role === 'user') {
      role = 'user'
      content = m.text
    } else {
      switch (m.kind) {
        case 'text':
          content = m.text
          break
        case 'review':
          // 卡片正文是空的（只有 reviewId）。存一句可读的占位，让导出的
          // 对话记录仍然连贯；真正还原成卡片靠 meta.kind。
          content = '[评审已创建]'
          meta = { kind: 'review', reviewId: m.reviewId }
          break
        case 'clarify':
          // 存成文字而不是可交互卡片：重放时那些候选项早就过期了，
          // 还原成按钮只会让用户点一个已经没有意义的选项。
          content = m.question
          break
        case 'confirm':
          content = `[确认评审方案：${m.intent.task_type || '未定'}]`
          break
        case 'error':
          // 瞬时错误提示不入库：重放时它没有意义，只会让历史对话里
          // 凭空多出几条早已不成立的报错。
          return
        default:
          return
      }
    }

    if (!content.trim()) return
    void ensureConversation().then((id) => {
      if (!id) return
      void api.appendConversationMessage(id, role, content, meta).catch(() => {
        // 静默：见上面的说明
      })
    })
  }

  const appendMessage = (m: ChatMessageBase) => {
    persistMessage(m)
    setMessages((prev) => [...prev, { ...m, ts: Date.now() }])
  }

  /** 追问模式下发送：同一个对话框、同一条消息列表，只是路由目标从
   * "意图解析→开新评审"换成"这条评审的 chat 接口"。用户说"就是要在同一个
   * 对话里聊"，所以这里绝不弹窗、绝不跳转，回复直接追加成普通聊天气泡。 */
  const sendFollowUp = async (rawText: string) => {
    if (!activeChatContext) return
    const imageCount = attachments.length
    // 只拖了图、一个字没打——发送按钮此前对这种情况是禁用的（判断只看
    // input.trim()，完全没考虑附件），点了跟没点一样，图片就一直卡在附件栏，
    // 零提示零反馈。现在只要有图或有字任一项就放行；纯图时补一句占位文字，
    // 后端 message 不能为空，且这句话也让追问历史看得懂"这轮问的是什么"。
    const text = rawText.trim() || (imageCount > 0 ? '（仅附图，无文字说明）' : '')
    if (!text) return
    setInput('')
    // 附件栏里的截图随追问一起发出去——此前这条链路只发文字，图片被静默
    // 丢弃（附件还挂在栏里，用户以为发出去了）。发送成功与否都先清空附件栏，
    // 跟"开新评审"链路的行为一致：一条消息带一批图，不粘到下一条。
    const imagePayload = attachments.map((a) => a.image_data)
    setAttachments([])
    appendMessage({
      id: nextId(),
      role: 'user',
      text,
      images: imagePayload.length > 0 ? imagePayload : undefined,
    })
    setBusy(true)
    try {
      const res = await api.sendReviewChat(
        activeChatContext.reviewId,
        text,
        activeChatContext.personaId,
        imagePayload,
      )
      appendMessage({
        id: nextId(),
        role: 'assistant',
        kind: 'text',
        text: res.reply.content,
        isGated: res.reply.is_gated,
        fullLength: res.reply.full_length ?? undefined,
      })
    } catch (e) {
      appendMessage({
        id: nextId(),
        role: 'assistant',
        kind: 'error',
        text: e instanceof Error ? e.message : '追问失败，请再试一次',
      })
    } finally {
      setBusy(false)
    }
  }

  const send = async (raw: string) => {
    if (busy) return
    if (activeChatContext) {
      return sendFollowUp(raw)
    }
    // 只拖了截图、一个字没打也要能发——发送按钮此前只看 input.trim()，
    // 纯图时按钮是禁用的，点了没反应，图片就一直卡在附件栏。这里放开：
    // 有图没字时用占位文字撑住"这条消息说了什么"，intent 解析拿不到有效
    // 文字信号大概率会追问，那也是诚实的行为，好过按钮直接摁不动。
    const text = raw.trim() || (attachments.length > 0 ? '（仅附图，无文字说明）' : '')
    if (!text) return
    setInput('')
    setShowExamples(false) // 开聊后收起示例，给对话让出空间
    // 图片跟着这条气泡一起露出来（不再是"发完文字、图还杵在附件栏里"），
    // 同时并入跨轮次的累积区——用户可能先发图被追问，几句之后才凑出
    // confirm 卡片，图不能因为这条消息"发送"了就在评审真正建出来之前被丢掉。
    const imagesForBubble = attachments.map((a) => a.image_data)
    sessionImagesRef.current = [...sessionImagesRef.current, ...attachments]
    setAttachments([])
    appendMessage({
      id: nextId(),
      role: 'user',
      text,
      images: imagesForBubble.length > 0 ? imagesForBubble : undefined,
    })
    historyRef.current = [...historyRef.current, text]
    setBusy(true)
    try {
      const combined = historyRef.current.join('\n')
      const parsed = await api.parseIntent(combined)
      // 钉住的技能/任务类型是用户明确选的，直接覆盖 AI 猜的结果——
      // 钉了任务类型就不用再走"置信度不够就追问"这一步。
      const intent: IntentResult = {
        ...parsed,
        task_type: pinnedTaskType ? (pinnedTaskType.id as IntentResult['task_type']) : parsed.task_type,
        skill_type: pinnedSkill ? (pinnedSkill.type as IntentResult['skill_type']) : parsed.skill_type,
        project_key: pinnedProject ?? parsed.project_key,
        needs_clarification: pinnedTaskType ? false : parsed.needs_clarification,
      }
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

  const handleFiles = async (files: FileList | File[] | null) => {
    if (!files || files.length === 0) return
    setUploading(true)
    // 以前这里每轮循环都读闭包里的 attachments.length 来判上限——那是本次渲染的
    // 快照，循环内不会变：一次多选或拖入 N 张图时每一轮读到的都是同一个旧长度，
    // 8 张上限被整批绕过（实测一次拖 20 张全都进来）。附件是全量驻留内存的
    // data URI，绕过上限就是把页面拖垮。
    // 现在两道闸：slots 在本批内自减（决定"还收不收、要不要提示"，同步可靠，
    // 也省掉注定要被丢弃的那次上传），setAttachments 用函数式更新在 prev 上再判
    // 一次（并发调用时的硬闸，满了就原样返回，绝不静默塞进去）。
    let slots = MAX_ATTACHMENTS - attachments.length
    let overflowed = false
    try {
      for (const file of Array.from(files)) {
        if (slots <= 0) {
          overflowed = true
          break
        }
        try {
          const result = await api.upload(file)
          if (result.kind === 'image') {
            slots -= 1
            const attachmentId = nextId() // 在 updater 外取 id：updater 保持无副作用
            setAttachments((prev) =>
              prev.length >= MAX_ATTACHMENTS
                ? prev
                : [
                    ...prev,
                    { id: attachmentId, filename: result.filename, image_data: result.image_data },
                  ]
            )
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
      if (overflowed) {
        appendMessage({
          id: nextId(),
          role: 'assistant',
          kind: 'error',
          text: `最多附带 ${MAX_ATTACHMENTS} 张图片——先移除几张再继续上传`,
        })
      }
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id))
  }

  // 拖拽/粘贴上传——和点击附件按钮走同一条 handleFiles 通道，行为完全一致
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.types.includes('Files')) setDragging(true)
  }
  const handleDragLeave = (e: React.DragEvent) => {
    if (e.currentTarget === e.target) setDragging(false)
  }
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    void handleFiles(e.dataTransfer.files)
  }
  const handlePaste = (e: React.ClipboardEvent) => {
    const files = Array.from(e.clipboardData.items)
      .filter((item) => item.kind === 'file')
      .map((item) => item.getAsFile())
      .filter((f): f is File => f !== null)
    if (files.length > 0) {
      e.preventDefault() // 有文件就按上传处理，不把图片当文本粘进输入框
      void handleFiles(files)
    }
  }

  const pickCandidate = (candidate: string) => {
    // 用户点了候选任务类型，等价于告诉助手"就是这个"，直接推进到确认卡片
    void send(`就是${TASK_LABELS[candidate] ?? candidate}`)
  }

  const confirmAndCreate = async (msgId: string, intent: IntentResult, personasOverride?: string[]) => {
    if (!intent.task_type) return
    // 全局防重：多张确认卡片共存时，任何一张在提交中都不允许再发——
    // 否则双击/连点会创建出两个评审
    if (submittingId !== null) return
    setSubmittingId(msgId)
    try {
      const artifactText = historyRef.current.join('\n')
      // 图片来源两处：sessionImagesRef 是"之前几轮发送时已经落进气泡"的累积图，
      // attachments 是"confirm 卡片出来后还没点发送、仍挂在附件栏"的图——
      // 两处都要带上，否则要么丢掉早前几轮的图，要么丢掉临门一脚才加的图。
      const allImages = [...sessionImagesRef.current, ...attachments]
      const materials: Material[] = [
        { type: 'text', text: intent.artifact_text || artifactText },
        ...allImages.map((a) => ({ type: 'image' as const, image_data: a.image_data, filename: a.filename })),
      ]
      const res = await api.createReview({
        task_type: intent.task_type,
        artifact: { title: artifactText.slice(0, 60), materials },
        mode: intent.mode,
        persona_pack: intent.persona_pack,
        selected_personas: (() => {
          const chosen = personasOverride ?? intent.matched_personas
          return chosen.length > 0 ? chosen : undefined
        })(),
        skill_type: intent.skill_type,
        project_key: intent.project_key,
      })
      // 高级技能次数用完被降级时，必须**在这里说出来**。后端已经把技能剥掉了，
      // 前端不吭声的话，用户看到的是一份悄悄少了一层的报告——他会以为产品
      // 本来就这样，而不知道自己刚用完免费次数。静默降级是这个仓库反复要根除的。
      if (res.skill_degraded) {
        appendMessage({
          id: nextId(),
          role: 'assistant',
          kind: 'text',
          text: `${res.skill_degraded}。想继续用可以兑换 CDK，或在设置页填写自己的 API Key（BYOK 不受此限制）。`,
        })
      }
      // 评审卡片直接嵌进这条对话——不跳走，用户可以边等边继续聊
      appendMessage({ id: nextId(), role: 'assistant', kind: 'review', reviewId: res.review_id })
      setAttachments([])
      sessionImagesRef.current = []
      void loadHistory() // 新评审马上出现在左侧历史里
      // 把评审关联到这段对话。弱引用：之后删掉评审不会连带删掉用户
      // 在评审之前打的那些字。
      void ensureConversation().then((cid) => {
        if (cid) void api.linkConversationReview(cid, res.review_id).catch(() => {})
      })
      // URL 同时带 c 与 review：
      //   c      —— 刷新后按真实记录还原整段对话（含评审创建前的多轮澄清）
      //   review —— 保持既有的分享/回访链接可用
      // 只写 review 会让刷新走回"从 artifact_bundle 反推一条用户气泡"的近似路径，
      // 把刚刚存下来的真实记录盖掉。
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('review', res.review_id)
          if (conversationIdRef.current) next.set('c', conversationIdRef.current)
          return next
        },
        { replace: true },
      )
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
  // 只有开场白、用户还没开口 —— 对话区此时是「空状态」，才允许挂环境浮尘
  const isEmptyChat = messages.length === 1 && !messages.some((m) => m.role === 'user')

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      <HistorySidebar
        open={sidebarOpen}
        history={reviewHistory}
        drafts={draftConvs}
        activeConversationId={searchParams.get('c')}
        onOpenConversation={(id) => {
          // 走 URL 而不是直接 setMessages：挂载时那段恢复逻辑已经能按 ?c=
          // 把整段对话还原回来，这里复用它，避免两套还原代码各自漂移。
          const next = new URLSearchParams(searchParams)
          next.set('c', id)
          next.delete('review')
          setSearchParams(next, { replace: true })
          window.location.reload()
        }}
        error={historyError}
        deletingId={deletingId}
        confirmingId={confirmingId}
        requiresLogin={historyRequiresLogin}
        onNewConversation={startNewConversation}
        // 列表现在是瘦身数据（没有 artifact_bundle/report_json），还原对话需要
        // 完整内容——点开时按 id 单独拉一次，跟刷新页面走的是同一条路径。
        onOpenReview={(r) => void fetchReview(r.id).then(openReviewConversation).catch(() => {})}
        onAskDelete={askDeleteHistory}
        onConfirmDelete={handleDeleteHistory}
        onCancelDelete={() => setConfirmingId(null)}
      />

      <div className="flex min-w-0 flex-1 flex-col px-6 py-6">
      <header className="mb-4 flex items-center gap-2">
        <button
          onClick={() => setSidebarOpen((v) => !v)}
          className="mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-muted hover:bg-bg-secondary hover:text-text-primary transition-colors"
          aria-label={sidebarOpen ? '收起历史侧栏' : '展开历史侧栏'}
          title={sidebarOpen ? '收起历史侧栏' : '展开历史侧栏'}
        >
          {sidebarOpen ? <PanelLeftClose className="h-4 w-4" strokeWidth={1.5} /> : <PanelLeftOpen className="h-4 w-4" strokeWidth={1.5} />}
        </button>
        <Sparkles className="h-5 w-5 text-brand-primary" strokeWidth={1.5} />
        <div>
          <h1 className="text-lg font-semibold text-text-primary font-display">对话评审</h1>
          <p className="text-xs text-text-muted">描述你要评审的内容，剩下的交给评审团</p>
        </div>
      </header>

      {config && !ready && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-warm-orange/40 bg-warm-orange/10 p-3 text-sm shrink-0">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warm-orange" strokeWidth={2} />
          <div>
            <p className="font-medium text-text-primary">请先配置 API Key</p>
            <p className="mt-1 text-text-secondary">
              评审需要调用真实模型，未配置 Key 无法开始。
              <button
                className="ml-1 text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim"
                onClick={() => navigate('/settings')}
              >
                去设置页填写
              </button>
            </p>
          </div>
        </div>
      )}

      <div
        ref={listRef}
        className={cn(
          // isolate：让浮尘层的负 z-index 被限制在这个容器内，只沉到自身背景之上、气泡之下
          'chat-backdrop relative isolate flex-1 space-y-4 overflow-y-auto rounded-xl border p-4 transition-colors',
          dragging ? 'border-brand-primary/60 bg-brand-primary/5' : 'border-border bg-bg-card/60'
        )}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* 浮尘只在「只有开场白、用户一句话都还没发」时出现：
            此时对话区基本是空的，需要一点氛围；一旦有真实对话就摘掉——
            正文文字底下飘东西会持续偷注意力。DOM 放在气泡前，天然在内容层下面 */}
        {isEmptyChat && <AmbientMotes className="-z-10" />}
        {messages.map((m) => (
          <ChatBubble
            key={m.id}
            message={m}
            busy={submittingId === m.id}
            onPickCandidate={pickCandidate}
            personaNames={personaNames}
            onConfirm={(intent, personas) => void confirmAndCreate(m.id, intent, personas)}
            onGoSettings={() => navigate('/settings')}
            onGoLogin={() => navigate('/login')}
            onStartFollowUp={(reviewId, personaId, label) => setActiveChatContext({ reviewId, personaId, label })}
          />
        ))}
        {busy && <ThinkingIndicator />}
        {dragging && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-xl border-2 border-dashed border-brand-primary/60 bg-bg-primary/70 backdrop-blur-sm">
            <p className="flex items-center gap-2 text-sm font-medium text-brand-primary">
              <ImageIcon className="h-5 w-5" strokeWidth={1.5} />
              松开以上传截图/文件
            </p>
          </div>
        )}
      </div>
      <p className="mt-1.5 flex items-center gap-1 text-[11px] text-text-muted shrink-0">
        <Paperclip className="h-3 w-3" strokeWidth={1.5} />
        支持拖拽文件到对话区，或 Ctrl+V 粘贴截图
      </p>

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
                className="rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary transition-all duration-150 hover:-translate-y-0.5 hover:border-brand-primary/40 hover:text-text-primary hover:shadow-[0_4px_16px_rgba(0,0,0,0.10)]"
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

      {activeChatContext && (
        <div className="mt-3 flex shrink-0 items-center justify-between gap-2 rounded-md border border-brand-primary/30 bg-brand-primary/10 px-2.5 py-1.5 text-xs text-brand-primary">
          <span className="flex items-center gap-1.5 truncate">
            <Sparkles className="h-3 w-3 shrink-0" strokeWidth={2} />
            正在追问 · {activeChatContext.label}
          </span>
          <button
            onClick={() => setActiveChatContext(null)}
            className="shrink-0 hover:text-text-primary transition-colors"
            aria-label="退出追问模式"
          >
            <X className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        </div>
      )}

      {(pinnedSkill || pinnedTaskType || pinnedProject) && (
        <div className="mt-3 flex flex-wrap gap-2 shrink-0">
          {pinnedSkill && (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-cyan/30 bg-cyan/10 px-2.5 py-1 text-xs text-cyan">
              <Zap className="h-3 w-3" strokeWidth={2} />
              技能 · {pinnedSkill.name}
              <button onClick={() => setPinnedSkill(null)} className="hover:text-text-primary transition-colors" aria-label="取消技能">
                <X className="h-3 w-3" strokeWidth={2} />
              </button>
            </span>
          )}
          {pinnedTaskType && (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-warm-orange/30 bg-warm-orange/10 px-2.5 py-1 text-xs text-warm-orange">
              <Target className="h-3 w-3" strokeWidth={2} />
              类型 · {pinnedTaskType.name}
              <button onClick={() => setPinnedTaskType(null)} className="hover:text-text-primary transition-colors" aria-label="取消类型">
                <X className="h-3 w-3" strokeWidth={2} />
              </button>
            </span>
          )}
          {pinnedProject && (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-warm-orange/30 bg-warm-orange/10 px-2.5 py-1 text-xs text-warm-orange">
              <FolderOpen className="h-3 w-3" strokeWidth={2} />
              项目 · {pinnedProject}
              <button onClick={() => setPinnedProject(null)} className="hover:text-text-primary transition-colors" aria-label="取消项目">
                <X className="h-3 w-3" strokeWidth={2} />
              </button>
            </span>
          )}
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

        <div className="h-9 w-px shrink-0 bg-border" aria-hidden="true" />

        {/* 三个"钉住选择"按钮共享一个浅色胶囊容器，和上传按钮的独立感区分开——
            视觉上明确"这一组都是覆盖 AI 猜测结果的手动指定"。 */}
        <div className="flex shrink-0 items-center gap-0.5 rounded-lg bg-bg-secondary/60 p-0.5">
        {/* 选技能：弹层里只列能真正影响评审 prompt 的两个技能（红队/受众面板）——
            合成试玩是默认流程没必要选，人格生成是完全不同的动作不该混进来。 */}
        <div className="relative shrink-0">
          <button
            className={cn(
              'flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
              pinnedSkill ? 'bg-cyan/15 text-cyan' : 'text-text-muted hover:bg-bg-secondary hover:text-text-primary'
            )}
            onClick={() => {
              setSkillPickerOpen((v) => !v)
              setTypePickerOpen(false)
            }}
            aria-label="选择技能"
            title="选技能——不用等 AI 猜，直接指定评审视角"
          >
            <Zap className="h-4 w-4" strokeWidth={2} />
          </button>
          {skillPickerOpen && (
            <div className="absolute bottom-full left-0 z-20 mb-2 w-64 rounded-xl border border-border bg-bg-card p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.12)]">
              {SKILLS.filter((s) => s.type === 'red_team_audience' || s.type === 'audience_panel').map((s) => (
                <button
                  key={s.type}
                  className="flex w-full flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-bg-card-hover"
                  onClick={() => {
                    setPinnedSkill({ type: s.type, name: s.name })
                    setSkillPickerOpen(false)
                  }}
                >
                  <span className="flex w-full items-center gap-1.5 text-sm font-medium text-text-primary">
                    {s.name}
                    {skillQuota[s.type] != null && (
                      <span
                        className={cn(
                          'ml-auto rounded px-1.5 py-0.5 text-[10px] font-normal',
                          (skillQuota[s.type] as number) > 0
                            ? 'bg-cyan/15 text-cyan'
                            : 'bg-text-muted/15 text-text-muted',
                        )}
                      >
                        {(skillQuota[s.type] as number) > 0
                          ? `剩 ${skillQuota[s.type]} 次免费`
                          : '免费次数已用完'}
                      </span>
                    )}
                  </span>
                  <span className="text-xs text-text-muted">{s.description_zh}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 选任务类型：可搜索列表，选中即钉住，绕开置信度不够时的追问一步 */}
        <div className="relative shrink-0">
          <button
            className={cn(
              'flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
              pinnedTaskType ? 'bg-warm-orange/15 text-warm-orange' : 'text-text-muted hover:bg-bg-secondary hover:text-text-primary'
            )}
            onClick={() => {
              setTypePickerOpen((v) => !v)
              setSkillPickerOpen(false)
            }}
            aria-label="选择评审类型"
            title="选评审类型——直接指定，不用等 AI 猜"
          >
            <Target className="h-4 w-4" strokeWidth={2} />
          </button>
          {typePickerOpen && (
            <div className="absolute bottom-full left-0 z-20 mb-2 w-72 rounded-xl border border-border bg-bg-card p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.12)]">
              <div className="flex items-center gap-1.5 border-b border-border px-2 py-1.5">
                <Search className="h-3.5 w-3.5 text-text-muted shrink-0" strokeWidth={2} />
                <input
                  autoFocus
                  value={typeSearch}
                  onChange={(e) => setTypeSearch(e.target.value)}
                  placeholder="搜索评审类型…"
                  className="w-full bg-transparent text-sm text-text-primary placeholder-text-muted outline-none"
                />
              </div>
              <div className="max-h-64 overflow-y-auto">
                {TASK_TYPES.filter((t) => t.name.includes(typeSearch) || t.id.includes(typeSearch)).map((t) => (
                  <button
                    key={t.id}
                    className="flex w-full flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left transition-colors hover:bg-bg-card-hover"
                    onClick={() => {
                      setPinnedTaskType({ id: t.id, name: t.name })
                      setTypePickerOpen(false)
                      setTypeSearch('')
                    }}
                  >
                    <span className="text-sm font-medium text-text-primary">{t.name}</span>
                    <span className="text-xs text-text-muted">{t.description}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 选/建长期评审项目：新建输入名字，或从历史里挑一个已有项目继续——
            钉住后同名的评审会在侧栏/历史页自动聚合，不用每次都在话里念"创建...长期评审项目"。 */}
        <div className="relative shrink-0">
          <button
            className={cn(
              'flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
              pinnedProject ? 'bg-warm-orange/15 text-warm-orange' : 'text-text-muted hover:bg-bg-secondary hover:text-text-primary'
            )}
            onClick={() => {
              setProjectPickerOpen((v) => !v)
              setSkillPickerOpen(false)
              setTypePickerOpen(false)
            }}
            aria-label="选择长期评审项目"
            title="加入长期评审项目——之后的评审会按项目名聚合成时间线"
          >
            <FolderOpen className="h-4 w-4" strokeWidth={2} />
          </button>
          {projectPickerOpen && (
            <div className="absolute bottom-full left-0 z-20 mb-2 w-72 rounded-xl border border-border bg-bg-card p-2 shadow-[0_12px_40px_rgba(0,0,0,0.12)]">
              <p className="px-1 pb-1.5 text-xs text-text-muted">新建项目</p>
              <div className="flex items-center gap-1.5">
                <input
                  autoFocus
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && newProjectName.trim()) {
                      setPinnedProject(newProjectName.trim())
                      setNewProjectName('')
                      setProjectPickerOpen(false)
                    }
                  }}
                  placeholder="给项目起个名字…"
                  className="w-full rounded-md border border-border bg-bg-secondary px-2 py-1.5 text-sm text-text-primary placeholder-text-muted outline-none focus:border-brand-primary/40"
                />
                <button
                  disabled={!newProjectName.trim()}
                  onClick={() => {
                    setPinnedProject(newProjectName.trim())
                    setNewProjectName('')
                    setProjectPickerOpen(false)
                  }}
                  className="shrink-0 rounded-md bg-brand-primary px-2.5 py-1.5 text-xs font-medium text-white disabled:opacity-40"
                >
                  创建
                </button>
              </div>
              {(() => {
                const existing = Array.from(new Set((reviewHistory ?? []).map((r) => r.project_key).filter((k): k is string => !!k)))
                if (existing.length === 0) return null
                return (
                  <>
                    <p className="px-1 pb-1 pt-2.5 text-xs text-text-muted">继续已有项目</p>
                    <div className="max-h-40 overflow-y-auto">
                      {existing.map((key) => (
                        <button
                          key={key}
                          className="flex w-full items-center gap-1.5 rounded-lg px-2 py-1.5 text-left text-sm text-text-primary transition-colors hover:bg-bg-card-hover"
                          onClick={() => {
                            setPinnedProject(key)
                            setProjectPickerOpen(false)
                          }}
                        >
                          <FolderOpen className="h-3.5 w-3.5 shrink-0 text-warm-orange" strokeWidth={1.5} />
                          <span className="truncate">{key}</span>
                        </button>
                      ))}
                    </div>
                  </>
                )
              })()}
            </div>
          )}
        </div>
        </div>

        <div className="h-9 w-px shrink-0 bg-border" aria-hidden="true" />

        <textarea
          ref={inputRef}
          // rows=1 是对齐的关键，不是样式偏好：容器用 items-end 底部对齐，而 textarea
          // 的文字**从顶部内边距往下排**。rows=2 会让盒子固定 56px（2×20 行高 + 16 内边距），
          // 底边和两侧 h-9(36px) 的按钮对齐，多出来的 20px 全压在文字上方——
          // 单行时看起来就是"文字比图标高一截"。rows=1 时 20+16=36，和按钮严丝合缝。
          // （min-h-[36px] 在 rows=2 下完全不起作用，它比固有高度小，我一开始就是在这里判断错的。）
          //
          // 代价是单行装不下长文，所以配一个 autoGrow：输入时按内容撑高，上限 max-h-40，
          // 超了内部滚动。这时 items-end 才真正发挥作用——框变高，按钮跟着停在底部。
          className="min-h-[36px] max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-sm leading-5 text-text-primary placeholder-text-muted outline-none disabled:opacity-50"
          rows={1}
          aria-label="评审输入"
          placeholder={
            activeChatContext ? `问问${activeChatContext.label}…（Enter 发送）` : '说说你想评审什么…（Enter 发送，Shift+Enter 换行）'
          }
          value={input}
          disabled={busy}
          onChange={(e) => { setInput(e.target.value); autoGrow(e.currentTarget) }}
          onPaste={handlePaste}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void send(input)
            }
          }}
        />
        <button
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-primary text-white shadow-[0_2px_10px_rgba(0,113,227,0.30)] transition-all duration-150 hover:bg-brand-primary-dim hover:shadow-[0_4px_16px_rgba(0,113,227,0.40)] disabled:opacity-50 disabled:shadow-none"
          onClick={() => void send(input)}
          disabled={busy || (!input.trim() && attachments.length === 0)}
          aria-label="发送"
        >
          {busy ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
          ) : (
            <Send className="h-4 w-4" strokeWidth={2} />
          )}
        </button>
      </div>
      {attachments.length > 0 && (
        <p className="mt-1.5 flex items-center gap-1 text-[11px] text-text-muted shrink-0">
          <ImageIcon className="h-3 w-3" strokeWidth={1.5} />
          {attachments.length} 张图片将随{activeChatContext ? '追问' : '评审'}一起发送给支持视觉的模型
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
    </div>
  )
}

/** 同 project_key 的评审聚合成一个长期项目组，其余保持原来的扁平列表——
 * history 本身已按 created_at 倒序，分组内 / 分组间顺序天然保留。 */
function groupHistoryByProject(history: ReviewListItem[]): { projects: { key: string; items: ReviewListItem[] }[]; ungrouped: ReviewListItem[] } {
  const projectOrder: string[] = []
  const projectMap = new Map<string, ReviewListItem[]>()
  const ungrouped: ReviewListItem[] = []
  for (const r of history) {
    if (r.project_key) {
      if (!projectMap.has(r.project_key)) {
        projectMap.set(r.project_key, [])
        projectOrder.push(r.project_key)
      }
      projectMap.get(r.project_key)!.push(r)
    } else {
      ungrouped.push(r)
    }
  }
  return { projects: projectOrder.map((key) => ({ key, items: projectMap.get(key)! })), ungrouped }
}

function HistorySidebar({
  open,
  history,
  drafts,
  activeConversationId,
  onOpenConversation,
  error,
  deletingId,
  confirmingId,
  requiresLogin,
  onNewConversation,
  onOpenReview,
  onAskDelete,
  onConfirmDelete,
  onCancelDelete,
}: {
  open: boolean
  history: ReviewListItem[] | null
  drafts: ConversationSummary[]
  activeConversationId: string | null
  onOpenConversation: (id: string) => void
  error: string | null
  deletingId: string | null
  confirmingId: string | null
  requiresLogin: boolean
  onNewConversation: () => void
  onOpenReview: (review: ReviewListItem) => void
  onAskDelete: (e: React.MouseEvent, id: string) => void
  onConfirmDelete: (e: React.MouseEvent, id: string) => void
  onCancelDelete: () => void
}) {
  return (
    <aside
      className={cn(
        'shrink-0 overflow-hidden border-r border-border bg-bg-secondary/60 transition-all duration-200',
        open ? 'w-64' : 'w-0 border-r-0'
      )}
    >
      <div className="flex h-full w-64 flex-col">
        <div className="shrink-0 p-3">
          <button
            onClick={onNewConversation}
            className="flex w-full items-center gap-2 rounded-xl border border-brand-primary/30 bg-brand-primary/10 px-3 py-2.5 text-sm font-semibold text-brand-primary transition-all hover:bg-brand-primary/20 hover:shadow-[0_2px_12px_rgba(0,113,227,0.12)]"
          >
            <Plus className="h-4 w-4" strokeWidth={2} />
            新建对话
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 pb-3">
          {/* 还没产出评审的对话。它们此前在这里完全不可见——侧栏只读评审列表，
              于是"聊到一半还没开评审"的内容关掉页面就永久消失。 */}
          {drafts.length > 0 && (
            <div className="mb-4">
              <div className="mb-2 flex items-center gap-1.5 px-1">
                <div className="h-4 w-[3px] rounded-full bg-text-muted/40" />
                <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted">
                  进行中的对话
                </p>
              </div>
              <div className="space-y-1">
                {drafts.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => onOpenConversation(c.id)}
                    className={cn(
                      'block w-full truncate rounded-lg px-2 py-1.5 text-left text-xs transition-colors',
                      c.id === activeConversationId
                        ? 'bg-brand-primary/10 text-brand-primary'
                        : 'text-text-secondary hover:bg-bg-card',
                    )}
                    title={c.title || '未命名对话'}
                  >
                    {c.title || '未命名对话'}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="mb-2 flex items-center gap-1.5 px-1">
            <div className="h-4 w-[3px] rounded-full bg-brand-primary/40" />
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-text-muted">评审历史</p>
          </div>

          {/* 加载失败 / 删除失败都走这里，必须是明确可见的一块，不能只是一行灰字 */}
          {error && (
            <div
              role="alert"
              className="mb-2 flex items-start gap-1.5 rounded-md border border-severity-critical/30 bg-severity-critical/10 px-2 py-1.5 text-[11px] leading-snug text-severity-critical"
            >
              <AlertTriangle className="mt-px h-3 w-3 shrink-0" strokeWidth={1.5} />
              <span className="min-w-0">{error}</span>
            </div>
          )}

          {history === null ? (
            <div className="flex items-center gap-2 px-1 py-3 text-xs text-text-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} />
              加载中…
            </div>
          ) : history.length === 0 ? (
            requiresLogin ? (
              // 空列表有两种完全不同的含义，必须分开说：
              // "你还没做过评审" vs "这台实例上历史要登录才看得到"。
              // 后者如果也显示成"还没有评审记录"，用户会以为自己的评审丢了。
              <div className="flex flex-col items-center gap-3 px-2 py-8 text-center text-xs text-text-muted rounded-xl bg-bg-card border border-border border-dashed">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-primary/10">
                  <LogIn className="h-5 w-5 text-brand-primary" strokeWidth={1.5} />
                </div>
                <span className="leading-relaxed">
                  登录后可以看到自己的评审历史
                  <br />
                  <span className="text-text-muted/70">未登录时的评审不会归到任何账号下</span>
                </span>
                <Link
                  to="/login"
                  className="rounded-lg border border-brand-primary/40 bg-brand-primary/10 px-3 py-1.5 text-[11px] font-medium text-brand-primary transition-colors hover:bg-brand-primary/20"
                >
                  去登录
                </Link>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 px-2 py-8 text-center text-xs text-text-muted rounded-xl bg-bg-card border border-border border-dashed">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-bg-secondary">
                  <Inbox className="h-5 w-5 text-text-muted" strokeWidth={1.5} />
                </div>
                <span>还没有评审记录</span>
                <span className="text-[10px] text-text-muted/70">开始一段新对话，评审结果会出现在这里</span>
              </div>
            )
          ) : (
            (() => {
              const { projects, ungrouped } = groupHistoryByProject(history)
              const renderItem = (r: ReviewListItem) => {
                const label = r.target_title || TASK_TYPES.find((t) => t.id === r.task_type)?.name || r.task_type
                // 二次确认直接长在这一行里。整行不再可点（避免"想点取消结果打开了评审"）。
                if (confirmingId === r.id) {
                  return (
                    <div
                      key={r.id}
                      role="alertdialog"
                      aria-label={`确认删除「${label}」`}
                      className="rounded-lg border border-severity-critical/40 bg-severity-critical/10 px-2 py-2"
                    >
                      <p className="mb-1.5 text-[11px] leading-snug text-text-secondary">
                        删除「<span className="text-text-primary">{label}</span>」？
                        <br />
                        报告、各角色意见、全部追问记录一起没，无法撤销。
                      </p>
                      <div className="flex gap-1.5">
                        <button
                          autoFocus
                          onClick={(e) => onConfirmDelete(e, r.id)}
                          disabled={deletingId === r.id}
                          className="flex items-center gap-1 rounded bg-severity-critical/85 px-2 py-1 text-[11px] font-medium text-white transition-colors hover:bg-severity-critical disabled:opacity-60"
                        >
                          {deletingId === r.id && (
                            <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
                          )}
                          删除
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            onCancelDelete()
                          }}
                          className="rounded border border-border px-2 py-1 text-[11px] text-text-secondary transition-colors hover:bg-bg-card-hover hover:text-text-primary"
                        >
                          取消
                        </button>
                      </div>
                    </div>
                  )
                }
                return (
                  <div
                    key={r.id}
                    onClick={() => onOpenReview(r)}
                    className="group flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-xs text-text-secondary transition-all hover:bg-bg-card hover:shadow-sm hover:text-text-primary border border-transparent hover:border-border"
                  >
                    <div className="h-1.5 w-1.5 shrink-0 rounded-full bg-brand-primary/30 group-hover:bg-brand-primary/60 transition-colors" />
                    <span className="min-w-0 flex-1 truncate">{label}</span>
                    {/* 删除按钮常驻可见（低对比度，hover/focus 才提亮）。
                        以前是 opacity-0 + group-hover 才显形：触屏没有 hover，
                        等于这台设备上根本删不掉；桌面端用户也压根发现不了。
                        p-1.5 + h-3.5 图标 ≈ 26px 命中区，配合行高够手指点。 */}
                    <button
                      onClick={(e) => onAskDelete(e, r.id)}
                      className="shrink-0 rounded p-1.5 text-text-muted/40 transition-colors hover:bg-severity-critical/10 hover:text-severity-critical focus-visible:bg-severity-critical/10 focus-visible:text-severity-critical focus-visible:outline-none group-hover:text-text-muted"
                      aria-label={`删除「${label}」`}
                      title="删除这条评审（会二次确认）"
                    >
                      <Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} />
                    </button>
                  </div>
                )
              }
              return (
                <div className="space-y-3">
                  {projects.map((group) => (
                    <div key={group.key}>
                      <div className="mb-1.5 flex items-center gap-1.5 px-1 text-[11px] font-semibold text-warm-orange">
                        <div className="flex h-5 w-5 items-center justify-center rounded bg-warm-orange/10">
                          <FolderOpen className="h-3 w-3 shrink-0" strokeWidth={1.5} />
                        </div>
                        <span className="min-w-0 flex-1 truncate">{group.key}</span>
                        <span className="shrink-0 text-text-muted font-normal">{group.items.length}</span>
                      </div>
                      <div className="space-y-0.5 border-l-2 border-border/60 pl-2.5">
                        {group.items.map(renderItem)}
                      </div>
                    </div>
                  ))}
                  {ungrouped.length > 0 && <div className="space-y-1">{ungrouped.map(renderItem)}</div>}
                </div>
              )
            })()
          )}
        </div>
      </div>
    </aside>
  )
}

type ReviewState = {
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  detail?: ReviewDetail
  error?: string
  /** 连接 / 同步的如实交代：同步失败、实时通道不可用、长时间没动静。
   *  一个不动的进度条必须配一句话，否则用户只会读成"卡死了"。 */
  notice?: string
}

/** WS 不通时轮询是唯一通道 */
const POLL_FAST_MS = 3000
/** WS 通时的保险丝：只为兜住"连着但事件没送达"，别打爆后端 */
const POLL_SLOW_MS = 15000
/** 多久没有任何进展就向用户交代一句 */
const STALL_HINT_SEC = 45

/** 追踪一个评审的实时状态——聊天卡片和历史侧栏弹窗共用这一份逻辑。
 *
 * 关键点：打开的可能是刚创建、正在跑的评审（WS 会实时推事件），
 * 也可能是历史里一个早就跑完的旧评审（WS 频道早就没人发事件了，
 * 直接订阅只会永远停在"评审中"）。所以先拉一次当前详情兜底：
 * 已经是终态就直接用，还在跑才订阅 WS + 常驻轮询。
 *
 * 为什么轮询必须常驻（这一版修的就是这个）：
 * 后端 ConnectionManager.broadcast 只推给当前在线连接，无重放无补发。
 * 旧实现只在 onUnavailable（重试耗尽）里才启动轮询，于是有三条永久 pending 的路：
 *   1. WS 一直卡在 connecting —— 既不 open 也不 close，没有任何回调会触发；
 *   2. WS 连上但事件没送达（事件名不匹配 / 某条代码路径没发 / 半开连接）；
 *   3. 断线重连成功 —— 断线期间的 review.completed 永久丢失，而重连成功
 *      又让 onUnavailable 永远不会触发。
 * 现在：订阅前就把轮询开起来，WS 通只降频不停表，终态是唯一的退出条件。 */
function useReviewStatus(reviewId: string | null): ReviewState {
  const [state, setState] = useState<ReviewState>({ status: 'pending', progress: 0 })

  useEffect(() => {
    if (!reviewId) return
    let active = true
    let done = false // 到过终态：所有定时器和连接都该停了
    let pollTimer: ReturnType<typeof setInterval> | null = null
    let pollIntervalMs = 0
    let stallTimer: ReturnType<typeof setInterval> | null = null
    let socket: ReturnType<typeof connectReviewSocket> | null = null
    let failures = 0
    let wsStatus: WsStatus = 'connecting'
    let lastActivity = Date.now()
    let lastStatus: 'pending' | 'running' = 'pending'

    // 换一条评审 / 组件卸载 / 到终态，都走这里——定时器不留活口
    const stopAll = () => {
      done = true
      if (pollTimer) clearInterval(pollTimer)
      pollTimer = null
      pollIntervalMs = 0
      if (stallTimer) clearInterval(stallTimer)
      stallTimer = null
      socket?.close()
    }

    /** 连接 / 停滞交代。优先级：同步失败 > 实时通道异常 > 长时间无进展 */
    const refreshNotice = () => {
      if (!active || done) return
      const idle = Math.round((Date.now() - lastActivity) / 1000)
      const syncSec = (wsStatus === 'open' ? POLL_SLOW_MS : POLL_FAST_MS) / 1000
      const notice =
        failures >= 2
          ? `无法同步评审进度（已连续失败 ${failures} 次），正在自动重试。评审在后台继续跑，不会因此中断。`
          : wsStatus === 'unavailable'
            ? `实时连接不可用，已改为每 ${POLL_FAST_MS / 1000} 秒主动同步一次进度。进度仍会更新，只是稍慢。`
            : wsStatus === 'reconnecting'
              ? '实时连接中断，正在重连；期间改用轮询同步进度。'
              : idle >= STALL_HINT_SEC
                ? `已有 ${idle} 秒没有新进展 —— 仍在处理中（某个人格的长文本推理可能比较久），每 ${syncSec} 秒会主动同步一次状态。`
                : undefined
      setState((s) => (s.notice === notice ? s : { ...s, notice }))
    }

    const finish = (detail: ReviewDetail) => {
      if (!active) return
      if (detail.status === 'completed') {
        setState({ status: 'completed', progress: 100, detail })
        stopAll()
      } else if (detail.status === 'failed') {
        setState({ status: 'failed', progress: 0, error: detail.error_message ?? '评审失败' })
        stopAll()
      }
    }

    /** 拉一次全量状态。返回是否已终态。轮询、首拉、重连补拉共用这一条路径 */
    const refreshOnce = async (): Promise<boolean> => {
      try {
        const d = await api.getReview(reviewId)
        if (!active || done) return true
        failures = 0
        if (d.status === 'completed' || d.status === 'failed') {
          finish(d)
          return true
        }
        const next = d.status === 'running' ? 'running' : 'pending'
        // 轮询拿到的状态变了也算"有进展"，重置停滞计时
        if (next !== lastStatus) {
          lastStatus = next
          lastActivity = Date.now()
        }
        setState((s) => (s.status === next ? s : { ...s, status: next }))
        refreshNotice()
        return false
      } catch {
        // 不静默吞：计数并在卡片上如实说"同步失败，正在重试"
        failures += 1
        refreshNotice()
        return false
      }
    }

    const ensurePolling = (intervalMs: number) => {
      if (done) return
      if (pollTimer && pollIntervalMs === intervalMs) return
      if (pollTimer) clearInterval(pollTimer)
      pollIntervalMs = intervalMs
      pollTimer = setInterval(() => void refreshOnce(), intervalMs)
    }

    // 先把兜底开起来，再去连 WS：WS 可能一直卡在 connecting，
    // 那种情况下没有任何回调会触发，靠回调启动轮询等于没有兜底。
    ensurePolling(POLL_FAST_MS)
    stallTimer = setInterval(refreshNotice, 5000)

    void refreshOnce().then((terminal) => {
      // 已是终态（历史里跑完的旧评审）：没有事件会再来，不订阅 WS。
      // 首拉失败也走下面订阅——轮询已经在跑，会自己重试。
      if (!active || done || terminal) return

      socket = connectReviewSocket(reviewId, {
        onEvent: (evt: WsEvent) => {
          if (!active || done) return
          lastActivity = Date.now()
          if (evt.event === 'review.progress') {
            const progress = (evt.data as { progress?: number }).progress
            setState((s) => ({ ...s, status: 'running', progress: progress ?? s.progress }))
          } else if (evt.event === 'review.started') {
            setState((s) => ({ ...s, status: 'running' }))
          } else if (evt.event === 'review.completed') {
            // 走 refreshOnce 而不是裸 getReview().then(finish)：那个没有 catch，
            // 一次网络抖动就会让卡片永远停在"评审中"（WS 此时已自己关掉了）
            void refreshOnce()
          } else if (evt.event === 'review.failed') {
            const err = (evt.data as { error?: string }).error
            setState({ status: 'failed', progress: 0, error: err ?? '评审失败' })
            stopAll()
          }
        },
        onOpen: ({ reconnected }) => {
          // WS 通了也**不停**轮询，只降频：broadcast 无补发，
          // "连着但事件没送达"时轮询是唯一能到达终态的路径
          ensurePolling(POLL_SLOW_MS)
          // 断线期间推的事件（尤其是 review.completed）永久丢失 → 重连必须补拉
          if (reconnected) void refreshOnce()
        },
        onStatusChange: (s) => {
          wsStatus = s
          refreshNotice()
        },
        onClose: () => ensurePolling(POLL_FAST_MS),
        onUnavailable: () => ensurePolling(POLL_FAST_MS),
      })
    })

    return () => {
      active = false
      stopAll()
    }
  }, [reviewId])

  return state
}

/** 评审状态的展示内容——聊天气泡和弹窗只是外壳不同，内容完全一致。 */
const RISK_BADGE: Record<string, { label: string; color: string; bg: string; border: string }> = {
  low: { label: '低风险', color: 'text-brand-primary', bg: 'bg-brand-primary/10', border: 'border-brand-primary/30' },
  medium: { label: '中风险', color: 'text-severity-medium', bg: 'bg-severity-medium/10', border: 'border-severity-medium/30' },
  high: { label: '高风险', color: 'text-warm-orange', bg: 'bg-warm-orange/10', border: 'border-warm-orange/30' },
  critical: { label: '极高风险', color: 'text-severity-critical', bg: 'bg-severity-critical/10', border: 'border-severity-critical/30' },
}

const SEVERITY_DOT: Record<string, string> = {
  low: 'bg-text-muted',
  medium: 'bg-severity-medium',
  high: 'bg-warm-orange',
  critical: 'bg-severity-critical',
}

function ReviewStatusBody({
  reviewState,
  onStartFollowUp,
}: {
  reviewState: ReviewState
  onStartFollowUp: (reviewId: string, personaId: string | null, label: string) => void
}) {
  const [reportOpen, setReportOpen] = useState(false)
  const risk = RISK_BADGE[reviewState.detail?.report?.executive_summary?.release_risk ?? '']

  return (
    <>
      {(reviewState.status === 'pending' || reviewState.status === 'running') && (
        <>
          <p className="flex items-center gap-2 font-medium text-text-primary">
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-primary" strokeWidth={2} />
            评审团正在评审中…
          </p>
          {/* shimmer-bar 挂在轨道外层：跑批时百分比会在某个人格思考时卡住十几秒，
              静止的条会被读成「卡死」，流光负责传达「还在跑」。仅此分支（pending/running）渲染 */}
          <div className="shimmer-bar mt-2.5 h-1.5 overflow-hidden rounded-full bg-bg-card">
            <div
              className="h-full rounded-full bg-brand-primary shadow-none transition-all duration-500"
              style={{ width: `${reviewState.progress}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-text-muted">跑完之前你可以继续在这聊别的，我不会打断你。</p>
          {/* 同步 / 停滞交代：进度条静止时必须说明白是"还在跑"还是"连不上了"，
              否则用户只能靠猜。文案由 useReviewStatus 按真实连接状态给出。 */}
          {reviewState.notice && (
            <p className="mt-1.5 flex items-start gap-1.5 text-xs leading-snug text-warm-orange">
              <AlertTriangle className="mt-px h-3 w-3 shrink-0" strokeWidth={1.5} />
              <span className="min-w-0">{reviewState.notice}</span>
            </p>
          )}
        </>
      )}

      {reviewState.status === 'failed' && (
        <div className="flex items-start gap-2">
          <FileWarning className="mt-0.5 h-4 w-4 shrink-0 text-severity-critical" strokeWidth={2} />
          <div>
            <p className="font-medium text-text-primary">评审失败了</p>
            <p className="mt-1 text-text-secondary">{reviewState.error}</p>
          </div>
        </div>
      )}

      {/* animate-pop-in：报告卡片顶替进度条这一刻需要一个落点，
          否则内容凭空换掉，用户不确定是跑完了还是界面抖了一下 */}
      {reviewState.status === 'completed' && (
        <div className="animate-pop-in rounded-lg border border-border/60 bg-bg-card/40 p-3.5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="min-w-0 truncate text-[15px] font-semibold text-text-primary font-display">
              {TASK_LABELS[reviewState.detail?.task_type ?? ''] ?? reviewState.detail?.task_type ?? '评审报告'}
            </h3>
            {risk && (
              <span className={cn('shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium', risk.color, risk.bg, risk.border)}>
                {risk.label}
              </span>
            )}
          </div>

          {reviewState.detail?.report?.executive_summary?.primary_recommendation && (
            <p className="mt-2 text-[13px] leading-relaxed text-text-secondary line-clamp-3">
              {reviewState.detail.report.executive_summary.primary_recommendation}
            </p>
          )}

          <div className="mt-3 flex items-center gap-3 text-[11px] text-text-muted">
            {(() => {
              // 匿名"体验版"里 persona_notes/priority_fixes 被裁空，真实条数在 gated_counts。
              // 卡片必须显示真实总数，否则看起来像"0 角色 0 修复项"的空壳（其实评审团真跑了）。
              const rep = reviewState.detail?.report
              const gated = rep?.gated_counts
              const fixCount = (rep?.priority_fixes?.length ?? 0) + (gated?.priority_fixes_hidden ?? 0)
              const personaCount = (rep?.persona_notes?.length ?? 0) + (gated?.persona_notes_hidden ?? 0)

              // 详情还没到手 / 报告体为空 —— 绝不能拿 0 冒充"评审出来就是 0 条"。
              // 一个 0 值行看起来跟正常结果一模一样，是这仓库反复犯的病：
              // 读不到就说读不到，别让空壳伪装成结论。
              if (!reviewState.detail) {
                return (
                  <span className="flex items-center gap-1">
                    <Loader2 className="h-3 w-3 animate-spin" strokeWidth={1.75} />
                    读取报告中…
                  </span>
                )
              }
              if (!rep || personaCount === 0) {
                return (
                  <span className="flex items-center gap-1 text-warm-orange">
                    <FileWarning className="h-3 w-3" strokeWidth={1.75} />
                    报告内容为空（没读到角色意见）
                  </span>
                )
              }
              return (
                <>
                  <span className="flex items-center gap-1">
                    <FileWarning className="h-3 w-3" strokeWidth={1.75} />
                    {fixCount} 条修复项
                  </span>
                  <span className="flex items-center gap-1">
                    <Sparkles className="h-3 w-3" strokeWidth={1.75} />
                    {personaCount} 位角色
                  </span>
                </>
              )
            })()}
            {reviewState.detail?.total_cost_usd !== undefined && (
              <span>${reviewState.detail.total_cost_usd.toFixed(3)}</span>
            )}
            {(reviewState.detail?.input_tokens || reviewState.detail?.output_tokens) ? (
              <span
                className="flex items-center gap-1"
                title={`输入 ${(reviewState.detail?.input_tokens ?? 0).toLocaleString('en-US')} · 输出 ${(reviewState.detail?.output_tokens ?? 0).toLocaleString('en-US')} token`}
              >
                <Coins className="h-3 w-3" strokeWidth={1.75} />
                {((reviewState.detail?.input_tokens ?? 0) + (reviewState.detail?.output_tokens ?? 0)).toLocaleString('en-US')} tok
              </span>
            ) : null}
          </div>

          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={() => setReportOpen(true)}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-md border border-brand-primary/30 bg-brand-primary/10 py-1.5 text-[13px] font-medium text-brand-primary transition-colors hover:bg-brand-primary/20"
            >
              查看完整报告
              <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
            {reviewState.detail && (
              <button
                onClick={() => onStartFollowUp(reviewState.detail!.id, null, '这份报告')}
                className="shrink-0 rounded-md border border-border bg-bg-card px-3 py-1.5 text-[13px] text-text-secondary transition-colors hover:text-text-primary"
                title="就在这条对话里继续追问，不用打开报告"
              >
                追问
              </button>
            )}
          </div>
        </div>
      )}

      {reportOpen && reviewState.detail && (
        <ReportModal detail={reviewState.detail} onClose={() => setReportOpen(false)} onStartFollowUp={onStartFollowUp} />
      )}
    </>
  )
}

/** 评审卡片"查看完整报告"打开的弹窗——摘要+优先修复项+角色简报，
 * 数据直接复用已经拉到手的 detail，不用再发一次请求。图表/persona 详细对比
 * 那些更重的可视化留在独立报告页，弹窗底部给一个入口跳过去。 */
function ReportModal({
  detail,
  onClose,
  onStartFollowUp,
}: {
  detail: ReviewDetail
  onClose: () => void
  onStartFollowUp: (reviewId: string, personaId: string | null, label: string) => void
}) {
  const summary = detail.report?.executive_summary
  const risk = RISK_BADGE[summary?.release_risk ?? '']
  const priorityFixes = detail.report?.priority_fixes ?? []
  const personaNotes = detail.report?.persona_notes ?? []
  const disagreements = detail.report?.major_disagreements ?? []
  const informationGaps = detail.report?.information_gaps ?? []

  // 立场分布——引擎不单独出这一项，现场从 persona_notes 统计成文字摘要
  // （不引图表库，弹窗里一行字就够看清"谁站哪边"）
  const stanceCounts = new Map<string, number>()
  for (const note of personaNotes) {
    const s = note.primary_stance || '未表态'
    stanceCounts.set(s, (stanceCounts.get(s) ?? 0) + 1)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-bg-primary/80 p-6 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] w-full max-w-xl flex-col rounded-xl border border-brand-primary/30 bg-bg-secondary shadow-[0_2px_12px_rgba(0,0,0,0.06)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-3.5">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold text-text-primary font-display">
              {TASK_LABELS[detail.task_type ?? ''] ?? detail.task_type}
            </h2>
            <p className="text-xs text-text-muted">完整报告</p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded p-1.5 text-text-muted transition-colors hover:bg-bg-card hover:text-text-primary"
            aria-label="关闭"
          >
            <X className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 text-sm">
          <div className="flex items-center gap-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">结论</p>
            {risk && (
              <span className={cn('rounded-full border px-2 py-0.5 text-[11px] font-medium', risk.color, risk.bg, risk.border)}>
                {risk.label}
              </span>
            )}
            {summary?.evidence_quality && (
              <span className="rounded-full border border-border bg-bg-card px-2 py-0.5 text-[11px] text-text-muted">
                证据 · {summary.evidence_quality}
              </span>
            )}
          </div>
          {summary?.primary_recommendation && (
            <p className="mt-1.5 leading-relaxed text-text-primary">{summary.primary_recommendation}</p>
          )}

          {priorityFixes.length > 0 && (
            <div className="mt-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                优先修复项 · {priorityFixes.length}
              </p>
              <div className="mt-2 space-y-2">
                {priorityFixes.map((fix, i) => (
                  <div key={i} className="flex gap-2 rounded-lg border border-border bg-bg-card/40 p-2.5">
                    <span
                      className={cn('mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full', SEVERITY_DOT[fix.severity ?? 'medium'])}
                    />
                    <div className="min-w-0">
                      <p className="font-medium text-text-primary">{fix.title}</p>
                      {fix.why_it_matters && <p className="mt-0.5 text-xs text-text-secondary">{fix.why_it_matters}</p>}
                      {fix.suggested_fix && (
                        <p className="mt-1 text-xs text-brand-primary">建议：{fix.suggested_fix}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {personaNotes.length > 0 && (
            <div className="mt-5">
              <div className="flex items-center justify-between">
                <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                  角色简报 · {personaNotes.length}
                </p>
                {stanceCounts.size > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    {Array.from(stanceCounts.entries()).map(([stance, count]) => (
                      <span key={stance} className="rounded-full border border-border bg-bg-card px-2 py-0.5 text-[11px] text-text-secondary">
                        {stance} · {count}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <div className="mt-2 space-y-1.5">
                {personaNotes.map((note, i) => (
                  <div key={i} className="flex items-center justify-between gap-2 rounded-lg bg-bg-card/40 px-2.5 py-2">
                    <span className="min-w-0 truncate text-text-primary">{note.persona_name ?? note.persona_id}</span>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="text-xs text-text-muted">
                        {note.primary_stance ?? '—'}
                        {note.key_issues && note.key_issues.length > 0 ? ` · ${note.key_issues.length} 条意见` : ''}
                      </span>
                      <button
                        onClick={() => {
                          onStartFollowUp(detail.id, note.persona_id, note.persona_name ?? note.persona_id)
                          onClose()
                        }}
                        className="rounded-full border border-brand-primary/30 bg-brand-primary/10 px-2 py-0.5 text-[11px] text-brand-primary transition-colors hover:bg-brand-primary/20"
                      >
                        跟TA聊聊
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {disagreements.length > 0 && (
            <div className="mt-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                主要分歧 · {disagreements.length}
              </p>
              <div className="mt-2 space-y-2">
                {disagreements.map((d, i) => (
                  <div key={i} className="rounded-lg border border-warm-orange/20 bg-warm-orange/5 p-2.5">
                    <p className="font-medium text-text-primary">{d.topic}</p>
                    {d.persona_stances && d.persona_stances.length > 0 && (
                      <ul className="mt-1 space-y-0.5 text-xs text-text-secondary">
                        {d.persona_stances.map((ps, j) => (
                          <li key={j}>
                            {ps.persona_id}：{ps.stance}
                            {ps.evidence ? `（${ps.evidence}）` : ''}
                          </li>
                        ))}
                      </ul>
                    )}
                    {d.resolution_suggestion && (
                      <p className="mt-1.5 text-xs text-brand-primary">调解建议：{d.resolution_suggestion}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {informationGaps.length > 0 && (
            <div className="mt-5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                信息缺口 · {informationGaps.length}
              </p>
              <ul className="mt-2 list-inside list-disc space-y-1 text-text-secondary">
                {informationGaps.map((gap, i) => (
                  <li key={i}>{gap}</li>
                ))}
              </ul>
            </div>
          )}

        </div>

        <div className="flex shrink-0 items-center justify-between gap-2 border-t border-border px-5 py-3 text-xs text-text-muted">
          <span>花费 ${detail.total_cost_usd.toFixed(3)}</span>
          <button
            onClick={() => {
              onStartFollowUp(detail.id, null, '这份报告')
              onClose()
            }}
            className="flex items-center gap-1.5 rounded-md border border-brand-primary/30 bg-brand-primary/10 px-2.5 py-1.5 text-[13px] font-medium text-brand-primary transition-colors hover:bg-brand-primary/20"
          >
            <Sparkles className="h-3.5 w-3.5" strokeWidth={2} />
            追问这份报告
          </button>
        </div>
      </div>
    </div>
  )
}

function ChatBubble({
  message,
  busy,
  personaNames,
  onPickCandidate,
  onConfirm,
  onGoSettings,
  onGoLogin,
  onStartFollowUp,
}: {
  message: ChatMessage
  busy: boolean
  personaNames: Record<string, string>
  onPickCandidate: (candidate: string) => void
  onConfirm: (intent: IntentResult, personas?: string[]) => void
  onGoSettings: () => void
  onGoLogin: () => void
  onStartFollowUp: (reviewId: string, personaId: string | null, label: string) => void
}) {
  const timeLabel = formatTime(message.ts)
  // 确认卡片上被用户手动移除的角色（呼叫角色可开庭前调整）。
  // hooks 必须在所有条件 return 之前调用，故放在这里而不是 confirm 分支里。
  const [removedPersonas, setRemovedPersonas] = useState<Set<string>>(new Set())

  // 评审卡片的进度追踪。hooks 必须在条件 return 之前，故对非 review 消息也声明
  // （reviewId 传 null 时 hook 内部直接跳过）。
  const reviewIdForEffect = message.role === 'assistant' && message.kind === 'review' ? message.reviewId : null
  const reviewState = useReviewStatus(reviewIdForEffect)

  if (message.role === 'user') {
    return (
      <div className="flex justify-end animate-message-in">
        <div className="flex max-w-[75%] flex-col items-end">
          {/* 图片本身要在气泡里露出来，跟正常聊天记录一样——之前只在文字里
           * 写一句"（附图×N）"，图片实际内容从没被渲染进对话，用户看不到
           * 自己发过什么图。 */}
          {message.images && message.images.length > 0 && (
            <div className="mb-1.5 flex flex-wrap justify-end gap-1.5">
              {message.images.map((src, i) => (
                <img
                  key={i}
                  src={src}
                  alt={`附图 ${i + 1}`}
                  className="h-20 w-20 rounded-lg border border-brand-primary/30 object-cover shadow-[0_2px_8px_rgba(0,0,0,0.08)]"
                />
              ))}
            </div>
          )}
          {message.text && (
            <div className="rounded-xl rounded-br-sm bg-brand-primary px-4 py-2.5 text-sm leading-relaxed text-white whitespace-pre-wrap shadow-[0_2px_10px_rgba(0,113,227,0.22)]">
              {message.text}
            </div>
          )}
          <span className="mt-1 font-mono text-[10px] tracking-wider text-text-muted">{timeLabel}</span>
        </div>
      </div>
    )
  }

  if (message.kind === 'text') {
    return (
      <div className="flex items-start gap-2.5 animate-message-in">
        <AssistantAvatar />
        <div className="flex max-w-[75%] flex-col">
          <div
            className={cn(
              'rounded-xl rounded-tl-sm border border-l-[3px] px-4 py-2.5 text-sm leading-relaxed text-text-primary',
              message.isGated
                ? 'border-warm-orange/30 border-l-warm-orange/50 bg-warm-orange/5'
                : 'border-border border-l-brand-primary/40 bg-bg-secondary',
            )}
          >
            {message.text}
            {message.isGated && (
              <div className="mt-2 flex items-center gap-2 border-t border-warm-orange/20 pt-2 text-xs text-text-muted">
                <span>
                  还有 {Math.max(0, (message.fullLength ?? 0) - message.text.length)} 字被隐藏
                </span>
                <button
                  onClick={onGoLogin}
                  className="font-medium text-brand-primary underline underline-offset-2 hover:text-text-primary"
                >
                  登录看完整回答
                </button>
              </div>
            )}
          </div>
          <span className="mt-1 font-mono text-[10px] tracking-wider text-text-muted">{timeLabel}</span>
        </div>
      </div>
    )
  }

  if (message.kind === 'error') {
    return (
      <div className="flex items-start gap-2.5 animate-message-in">
        <AssistantAvatar />
        <div className="flex max-w-[75%] flex-col">
          <div className="rounded-xl rounded-tl-sm border border-severity-critical/40 border-l-[3px] border-l-severity-critical bg-severity-critical/10 px-4 py-2.5 text-sm leading-relaxed text-text-primary">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-severity-critical" strokeWidth={2} />
              <div>
                {message.text}
                {message.needsKey && (
                  <button
                    className="ml-2 text-brand-primary underline underline-offset-2 hover:text-text-primary"
                    onClick={onGoSettings}
                  >
                    去填写 API Key
                  </button>
                )}
              </div>
            </div>
          </div>
          <span className="mt-1 font-mono text-[10px] tracking-wider text-text-muted">{timeLabel}</span>
        </div>
      </div>
    )
  }

  if (message.kind === 'review') {
    return (
      <div className="flex items-start gap-2.5 animate-message-in">
        <AssistantAvatar />
        <div className="flex w-full max-w-[85%] flex-col">
          <div className="rounded-xl rounded-tl-sm border border-brand-primary/30 bg-bg-secondary px-5 py-4 text-sm shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
            <ReviewStatusBody reviewState={reviewState} onStartFollowUp={onStartFollowUp} />
          </div>
          <span className="mt-1 font-mono text-[10px] tracking-wider text-text-muted">{timeLabel}</span>
        </div>
      </div>
    )
  }

  if (message.kind === 'clarify') {
    return (
      <div className="flex items-start gap-2.5 animate-message-in">
        <AssistantAvatar />
        <div className="flex max-w-[80%] flex-col">
          <div className="rounded-xl rounded-tl-sm border border-border border-l-[3px] border-l-brand-primary/40 bg-bg-secondary px-4 py-3 text-sm">
            <p className="leading-relaxed text-text-primary">{message.question}</p>
            {message.candidates.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {message.candidates.map((c) => (
                  <button
                    key={c}
                    className="rounded-md border border-border bg-bg-card px-3.5 py-2 text-sm text-text-primary transition-all duration-150 hover:-translate-y-0.5 hover:border-brand-primary/50 hover:bg-bg-card-hover hover:shadow-[0_4px_16px_rgba(0,0,0,0.10)]"
                    onClick={() => onPickCandidate(c)}
                  >
                    {TASK_LABELS[c] ?? c}
                  </button>
                ))}
              </div>
            )}
          </div>
          <span className="mt-1 font-mono text-[10px] tracking-wider text-text-muted">{timeLabel}</span>
        </div>
      </div>
    )
  }

  // confirm —— 转化关键节点：大标题 + 把握可视化 + 次要信息 chip 化
  const intent = message.intent
  const conf = confidenceLevel(intent.confidence)
  const activePersonas = intent.matched_personas.filter((id) => !removedPersonas.has(id))
  return (
    <div className="flex items-start gap-2.5 animate-message-in">
      <AssistantAvatar />
      <div className="flex w-full max-w-[85%] flex-col">
        <div className="rounded-xl rounded-tl-sm border border-brand-primary/30 bg-bg-secondary px-5 py-4 text-sm shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">我明白了，你想做的是</p>
          <h3 className="mt-1.5 text-base font-semibold text-text-primary font-display">
            {TASK_LABELS[intent.task_type ?? ''] ?? intent.task_type}
          </h3>

          <div className="mt-2.5 flex flex-wrap gap-2">
            <span className="rounded-md border border-border bg-bg-card px-2.5 py-1 text-xs text-text-secondary">
              深度 · {intent.mode}
            </span>
            <span className="rounded-md border border-border bg-bg-card px-2.5 py-1 text-xs text-text-secondary">
              评审团 · {intent.persona_pack}
            </span>
            {intent.skill_type && (
              <span className="rounded-md border border-cyan/30 bg-cyan/10 px-2.5 py-1 text-xs text-cyan">
                技能 · {SKILL_LABELS[intent.skill_type] ?? intent.skill_type}
              </span>
            )}
            {intent.project_key && (
              <span className="rounded-md border border-warm-orange/30 bg-warm-orange/10 px-2.5 py-1 text-xs text-warm-orange">
                项目 · {intent.project_key}
              </span>
            )}
          </div>

          {intent.matched_personas.length > 0 && (
            <div className="mt-3">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">
                指定角色（点 × 可移除，移除全部则回到自动选人）
              </p>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {intent.matched_personas.map((pid) => {
                  const removed = removedPersonas.has(pid)
                  const label = personaNames[pid] ?? pid
                  return (
                    <span
                      key={pid}
                      className={cn(
                        'inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-all',
                        removed
                          ? 'border-border bg-bg-card text-text-muted line-through opacity-60'
                          : 'border-cyan/30 bg-cyan/10 text-cyan'
                      )}
                    >
                      {label}
                      <button
                        onClick={() =>
                          setRemovedPersonas((prev) => {
                            const next = new Set(prev)
                            if (next.has(pid)) next.delete(pid)
                            else next.add(pid)
                            return next
                          })
                        }
                        className="ml-0.5 hover:text-text-primary transition-colors"
                        aria-label={removed ? `恢复 ${label}` : `移除 ${label}`}
                        title={removed ? '点击恢复' : '点击移除'}
                      >
                        {removed ? '↺' : '×'}
                      </button>
                    </span>
                  )
                })}
              </div>
            </div>
          )}

          <div className="mt-3.5">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-muted">匹配把握</span>
              <span className="font-medium text-text-secondary">
                {conf.label}（{(intent.confidence * 100).toFixed(0)}%）
              </span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-bg-card">
              <div
                className={`h-full rounded-full ${conf.barClass} shadow-none transition-all`}
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
            className="mt-4 w-full rounded-md bg-brand-primary py-2.5 font-semibold text-white shadow-[0_2px_10px_rgba(0,113,227,0.25)] transition-all duration-150 hover:bg-brand-primary-dim hover:shadow-[0_4px_16px_rgba(0,113,227,0.35)] disabled:opacity-50"
            onClick={() => onConfirm(intent, activePersonas)}
            disabled={busy}
          >
            {busy ? '开庭中…' : '开庭评审 →'}
          </button>
        </div>
        <span className="mt-1 font-mono text-[10px] tracking-wider text-text-muted">{timeLabel}</span>
      </div>
    </div>
  )
}
