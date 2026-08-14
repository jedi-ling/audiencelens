/**
 * 评审历史页。owner: agent-10。
 *
 * ── 顶部计数是全仓最典型的复数陷阱（契约 3.4 例 3/4/5）──
 * 原代码是一个三元的**四个**分支：
 *   total === null && loaded > 0   → 已显示 N 条
 *   total === null && loaded === 0 → ''            ← 空串分支
 *   有更多没加载               → 共 M 条 · 已显示 N 条
 *   全加载完                   → 共 M 条
 * 前三个进 count 块，**空串分支不进 key 表**——它不是一句"什么都不说"的文案，
 * 它是"这一整块不渲染"。给它一条空 key 会让 i18n:check 以为有人漏译了，
 * 而且下一个人看到 '' 会想"这里是不是该补一句"。条件渲染保留在 tsx 里。
 *
 * count.total_and_loaded 一句里有两个计数。复数只能挂一个（ICU 同限制），
 * 这里挂总数，所以**总数这个变量必须叫 count**——runtime 的变体解析只认
 * vars.count（见 runtime.ts 的 lookup），叫 total 的话 en 侧写了 _one/_other
 * 也永远选不中，反而会因为没有裸 key 而渲染成 ⟦missing:…⟧。
 * 已显示数当普通插值 {{loaded}}。
 *
 * ── 状态与模式徽章 ──
 * 这两组文案在 ReviewProgressPage / ReportPage / CreateReviewPage 里逐字重复，
 * 但那三个文件属于别的 agent。按契约 §11 判断树第 4 条：逐字相同也**各抽各的**，
 * 由 batch-0 决定要不要提到 enum.*，页面 agent 不替别人决定。
 */
import type { Messages } from '@/i18n/types'

export default {
  'meta.title': '评审历史',
  'header.title': '评审历史',
  'header.desc': '你发起过的所有评审，点进去看报告或继续跟进',

  // ---- 顶部计数（三分支，见文件头） ----
  'count.loaded_only': '已显示 {{count}} 条',
  'count.total_and_loaded': '共 {{count}} 条 · 已显示 {{loaded}} 条',
  'count.total': '共 {{count}} 条',

  // 评审状态徽章（等待中/运行中/已完成/失败/已取消）**曾经在这里**，集成期搬走了。
  // 它的键是后端 reviews.status 的取值，按契约 §11 判断树第 3 条属 enum.* 域；
  // 留在 page.history 会和 ReviewProgressPage 各持一份，正是 D5 要防的两个 owner。
  // 现在两页都读 enum.review_status.*（owner 在那个文件的头部写了来龙去脉）。

  // 评审模式徽章（快速/标准/完整）不在这里：它是后端枚举的标签，按契约 §11
  // 判断树第 3 条直接读 enum.mode_badge.*（owner: agent-1）。页面 agent 读 enum.* 是
  // 契约 4.3 规定的形态，不是越界。

  // ---- 空状态。两种"列表是空的"必须分清，否则用户以为记录被删了 ----
  'list_empty.title': '还没有评审记录',
  'list_empty.cta': '发起第一次评审 →',
  'load_error.title': '没能加载评审历史',
  'load_error.desc': '这不代表记录被删除了，请重试或稍后再来',

  // ---- 错误横幅。这三条是 tApiError 的 fallbackKey：只有在拿到的不是
  //      ApiError（网络断了、代码抛了 TypeError）时才会显示 ----
  'load.error': '加载失败',
  'load_more.error': '加载更多失败',
  'delete.error': '删除失败',

  // ---- 翻页出口 ----
  'load_more.cta': '加载更多',
  // 间隔号进值里，不留在 tsx 里拼。留在 tsx 里的话它就是一个绕过 key 表的
  // 中文标点（i18n-scan 会如实报出来），而且英文侧未必想用同一个分隔符。
  'load_more.remaining': '· 还有 {{count}} 条',
  'load_more.success': '已加载全部 {{count}} 条评审',

  // ---- 行内二次确认。**不是 window.confirm**：Chrome 连弹几次后会给出
  //      "阻止此页面创建更多对话框"，勾上之后 confirm() 静默返回 false，
  //      表现就是"删不掉"且没有任何报错。理由原文在 ReviewHistoryPage 的注释里 ----
  'confirm_dialog.aria': '确认删除「{{title}}」',
  // 两个 slot 的排版不同（标题是主色、后果说明是小字弱色），所以不能拆成两条 key——
  // 拆了英文语序就改不动了。单层不嵌套，<br/> 是特殊 void slot（契约 D13）。
  'confirm_dialog.desc':
    '删除「<name>{{title}}</name>」？<br/><note>报告、各角色意见、全部追问记录一起没，无法撤销。</note>',
  'item.aria': '删除「{{title}}」',
  'item.tooltip': '删除这条评审（会二次确认）',

  // ---- 长期评审项目分组 ----
  'group.meta': '长期评审项目 · {{count}} 次评审',
} satisfies Messages
