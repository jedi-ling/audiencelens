/**
 * 营销落地页（`/`）。owner: 落地页 agent。
 *
 * ⚠ 这个文件只有一条 key，这不是漏做。落地页正文走**另一条路线**（契约 4.4）：
 * 正文是 landing-body.html / landing-body.en.html 两份整块 HTML，由
 * LandingPage.tsx 按 ui_lang 选一份 ?raw 注入，**不进 key 表**。
 *
 * 为什么正文不抽 key：
 *   1. tests/test_landing_capability_claims.py 与 test_public_claims.py 都直接
 *      对 landing-body.html 做中文短语 / 数字断言。把正文打散成两百条 key 之后，
 *      那两套断言的比对对象就没了；而前者在短语找不到时走 pytest.skip 而不是
 *      fail——断言会**全部静默跳过而测试依然全绿**。
 *   2. 落地页几乎每个标题都被 <br> 和 <span class="gold"> 切断，中英文语序不同，
 *      断行位置也不同。逐句抽 key 会把断行结构一起冻死在中文语序上。
 *
 * 所以这里只留浏览器标题——它不在正文 HTML 里，必须走 i18n。
 */
import type { Messages } from '@/i18n/types'

export default {
  // 套进 common.meta.title_template 后是「上线前的 AI 评审团 · AudienceLens」。
  // 刻意不复用 nav.item.home（「首页」）：标签页 / 收藏夹 / 分享预览里看到的
  // 应该是这个站是干什么的，不是它在导航条里排第几个。
  'meta.title': '上线前的 AI 评审团',
} satisfies Messages
