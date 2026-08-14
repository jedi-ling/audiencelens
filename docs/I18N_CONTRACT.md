# AudienceLens 国际化实施契约

> 本文是**可执行契约**，不是设计讨论。接下来约 12 个 agent 会并行按它改不同页面，
> 所以这里的每一条都写成"必须/禁止"，凡是能有两种理解的地方都已经裁掉一种。
>
> 与它相关的文档：全链路架构看 [ARCHITECTURE.md](ARCHITECTURE.md)，
> 运维看 [MAINTENANCE.md](MAINTENANCE.md)。
>
> **裁决优先级**：本文 > 三份架构提案 > 个人判断。
> 提案之间打架的地方，本文第 2 节逐条给了裁决与理由，不要再回去读提案原文重新决定。
> 本文没写到的情况，**停下来问，不要自己定**——这是 12 个 agent 并行时唯一安全的做法。

---

## 0. 先统一三个被混为一谈的词

全仓此前把"语言"当成一个变量在讨论，实际上它是三个互不相干的东西。
本文之后所有地方一律用这三个词，不许再写裸的"语言 / language / locale"。

| 术语 | 是什么 | 生命周期 | 通道 | 本期状态 |
|---|---|---|---|---|
| **ui_lang** | 界面文案的语言 | 随时可切，纯客户端状态 | 不上行 | 本期主体工作 |
| **report_lang** | 一次评审**产出物**的语言 | 入队瞬间冻结，与 Review 行同生共死 | POST body 显式字段 → 落库 → 进引擎 | 本期只通管道，取值集合只有 `zh-CN` |
| **response_lang** | 单次 HTTP 响应里**后端系统文案**的语言 | 逐请求 | 无（本期不协商，见 D3） | 本期不做 |

为什么必须拆开：ui_lang 切换是"此刻的界面状态"，切了立刻生效没有竞态；
report_lang 是花了真钱产出的、不可变的资产属性，执行期读用户当前偏好会产生
"库里标 en、正文是 zh"的系统性撒谎；response_lang 是协商语义。
三者用同一个变量传，必然出现"用户切了界面语言 → 半小时后跑完的报告语言变了"这种没人能解释的行为。

---

## 1. 本期范围与不做清单

### 1.1 本期做

1. 前端 41 个文件的 UI 文案抽 key，zh / en 两份资源同时交付。
2. 自研 `src/i18n/` 运行时（约 300 行）+ codegen + 构建期卡口。
3. ui_lang 的状态、持久化、切换、`<html lang>` / `document.title` / `meta description` 同步。
4. 日期 / 数字 / 字节 / 百分比格式化统一收口 + eslint 钉死。
5. 后端目录数据（任务类型 / 评审模式 / 技能 / 人格包）双发英文字段。
6. `reviews.report_lang` 列 + 入队冻结 + 打通到 `run_panel` + `report_json.meta.language`。
7. 报告语言横幅（登录态与分享页两套措辞）。
8. `AppError` 信封新增 `message_lang`，前端据此决定显不显示后端中文。

### 1.2 本期明确不做（并且不许顺手做）

- **不做后端错误消息目录**（`message_key` → 模板）。理由见 D2。
- **不发 `Accept-Language` 请求头**。理由见 D3——发一个没有任何消费方的头，
  会让后来的人以为"语言已经传下去了"，这正是本仓最忌讳的形态。
- **不做英文报告**。`SUPPORTED_REPORT_LANGS = ("zh-CN",)`，前端不出"报告语言"选项。
  英文报告的前置硬门见第 10 节，一条都没做完之前把选项摆出来就是把"做不到"伪装成"支持"。
- **不做人格身份本地化**。结论见第 10.3 节，这是终局结论不是本期取舍。
- **不新建 404 页面**、不改路由、不改任何 CSS / 布局 / 配色。
  发现英文文案撑破容器：**记下来写进你的交付报告，不要自己改样式**。
  12 个 agent 各改各的 Tailwind class 会把设计系统改成 12 种样子。
- **不删 `src/temp/**`**（371 行死代码）。它已被 `tsconfig.app.json` 排除，
  不进类型检查也不进打包。删它是另一件事，本期只是不翻译它。
- **不动 `audiencelens-v0.2-harness/`**。它是 vendored 的外部 v0.2 制品，
  自带 LICENSE，动一个字之后每次升级都是合并冲突。

### 1.3 英文 UI 的上线开关

英文资源要写全（否则 `i18n:check` 红），但**英文界面默认不对用户可见**：

```ts
// src/i18n/locale.ts
// 可选语言由构建期环境变量决定，默认只有 zh。
// 为什么要这个开关：法务页译文需要复核、落地页英文断言测试还没写、
// 后端目录英文还没上线——这三件事都不是页面 agent 能独立完成的，
// 但它们没完成之前，英文界面就是一个"看起来支持、实际上有洞"的东西。
export const LOCALES = (import.meta.env.VITE_AL_LOCALES ?? 'zh').split(',') as Locale[]
```

`VITE_AL_LOCALES=zh,en` 时语言切换器才出现在设置页与页脚。
开发期请用 `VITE_AL_LOCALES=zh,en npm run dev` 自测你写的英文。

---

## 2. 提案分歧裁决（D1–D14）

每条都有编号，写代码时如果觉得"这里应该反过来做"，请引用编号来讨论，不要直接改。

### D1 · 用自研运行时，不引 react-i18next / lingui

**裁决**：自研 `src/i18n/`。

**理由**：不是"轻"。是三条硬需求现成库都要被改造着用，而改造完剩下的库价值只有插值：

- i18next 的核心契约 `fallbackLng` 的设计目的就是"缺了就悄悄用另一种语言"，
  产出的正是纪律 2 明令禁止的"英文界面混中文、无痕迹"；关掉它就退化成显示裸 key。
  要合规必须同时接管 `fallbackLng` + `missingKeyHandler` + `parseMissingKeyHandler`。
- 约 2000 个 key 要在 `tsc` 阶段报错，需要 codegen 出字面量联合类型，任何库都不提供。
- i18next 的 `Trans` 用位置索引 `<0>/<1>`，改 JSX 顺序会**静默错位**——文案照样渲染、没人发现。
  比自己写具名 slot 更危险。
- lingui 靠 babel/SWC 宏（`vite.config.ts` 现在没有插件位），且 `lingui extract`
  全量重写单个 catalog 文件——12 个 agent 并行时每人跑一次抽取都在改同一份资源，是冲突制造机。

库真正值钱的部分（远程加载器、命名空间懒加载、ICU 解析器、语言检测插件链）本仓一个都用不上：
纯客户端 Vite、只有 zh/en、22 个路由已按页 lazy 分割、复数用 `Intl.PluralRules` 就够。

### D2 · 后端错误消息：本期不做后端目录，前端按 code 出译文；但后端必须现在就加 `message_lang`

**分歧**：提案 A 说前端按 code 翻；提案 B 说后端按 `Accept-Language` 出 message + `message_key`；
提案 C 说后端零 locale 基建、不协商。

**裁决**：分两期，本期做前端侧 + 一个后端最小改动。

本期：
1. 后端 `AppError.to_payload()` 新增 `"message_lang": "zh-CN"` 常量字段。
   它不是协商结果，就是一句诚实的事实标注：**这条 message 是中文**。
2. 前端 `tApiError(e, fallbackKey)`：
   - `ui_lang === 'zh'` → 用后端 `message`（后端更具体，10 个 code 撑不起 174 个 raise 点）。
   - `ui_lang !== 'zh'` → 按 `error.<code>` 出前端译文（10 条，粒度粗但语种正确），
     后端原文降级成 `detail`（折叠 / `title` 属性）而不是丢弃。

**为什么不本期做后端目录**：后端 174 个含中文的 raise 点共用 10 个 code，
`bad_request` 一个码覆盖 75 段不同中文；`api/__init__.py` 还有 17 处走
`{"detail": ...}` 的第二套信封且**本身就中英混用**（同样是 404，评审返回英文
`Review not found`、文件解析返回中文）。把两套信封收敛 + 补细粒度 code 是一条
独立的、比本期还大的工作线，让 12 个前端 agent 等它，本期什么都做不了。

**为什么 `message_lang` 不能等**：没有它，前端无法判断自己拿到的 message 是不是英文，
只能猜。而猜出来的结果一旦错了，表现就是"英文界面混中文且没人发现"。
这个字段是纪律 2 在错误链路上的唯一落点，成本是 `errors.py` 加一行。

**必须在前端写死的注释**（`src/i18n/api-error.ts` 文件头）：
> 这是止血，不是解。10 个 code 撑不起后端 174 个 raise 点，
> 英文用户会看到大量"请求参数有误"这种没有信息量的粗译文。
> 真解在后端补细粒度 code + 消息目录，不要因为这层能跑就以为问题解决了。

### D3 · 本期不发 `Accept-Language`

**分歧**：提案 B 要发（标准头、代理天然 Vary）；提案 C 不发（后端零 locale 基建）。

**裁决**：不发。

**理由**：后端本期没有任何代码会读它（D2 已裁定不做协商）。发一个没有消费方的请求头，
唯一的效果是让下一个人打开 DevTools 看到 `Accept-Language: en` 之后以为语言已经传下去了，
然后花半天找"为什么后端不生效"。这是把"没做"伪装成"做了"。

**允许做的**：在 `apiClient.ts` 的 `request()` 里留一条注释标出注入点，写明为什么现在不注入。
真要发的那天，`request()` 是全站唯一 fetch 出口，加一行即全站生效——这个前提本来就成立，不用提前占位。

### D4 · 目录数据：后端双发英文字段，不协商、不加列、不建翻译表

**裁决**：任务类型 / 评审模式 / 技能在原 dict 里加**同级键**（`name_en` / `description_en` /
`stance_labels_en`），英文文案物理上放旁挂 JSON（`web/backend/app/i18n/catalog.en-US.json`），
import 期查表合并。端点签名一个字不改，没有 `lang` 参数、没有 `Accept-Language` 分支。

**理由**：
- "加 `name_en` 列"无列可加——26 张表没有一张是目录表，目录是
  `services/__init__.py` 的 Python 字面量 + `src/personas/*.yaml`。
- 建翻译表 = 给一份代码常量配一套 CRUD + 缓存失效 + 备份，
  还会让三道现成卡口（前端字面量 parity、引擎↔后端表比对、import 期 assert）失去比对对象。
- 协商会让同一个 URL 对不同客户端返回不同值。admin 后台与用户前端共用
  `platform.py` 的同一批 raise 点，协商一旦生效，运维在后台看到的语言取决于
  他浏览器的 `Accept-Language`——两边行为分叉且不可解释。双发从结构上消掉这个问题。
- 目录一共 14 任务类型 + 3 模式 + 4 技能 + 72 人格，双发的载荷代价可忽略；
  而"两个字段都在"让缺译可以被一条 CI 断言抓住。

**代价（接受）**：落到第三种语言时字段名会难看（`name_ja`）必须重构成嵌套。
重构面只有这几十条静态数据，到时候再说。

### D5 · 前端目录 overlay 的定位：离线兜底，不是事实源

**裁决**：目录文案的事实源分层写死如下，**一个条目的英文文案只能有一个 owner**。

| 目录 | zh 事实源 | en 事实源 | 前端 overlay 的作用 |
|---|---|---|---|
| TASK_TYPES / REVIEW_MODES / SKILLS / personas / packs | 后端 | **后端** `catalog.en-US.json` | 仅后端拉不到时的离线兜底 |
| TASK_MATERIALS 的 label / placeholder | 前端 `mock-data.ts` | **前端** `catalog.material.ts` | 唯一事实源（后端只有 key，没有 label） |
| EVALUATION_DIMENSIONS / PACK_NAME_MAP / AXIS_LABEL_MAP / BEHAVIOR_AXES | 前端 | **前端** | 唯一事实源 |

前端离线兜底那份英文（`locales/en/catalog.task_type.ts` 等）**不许手写**，
由 `npm run i18n:sync-catalog` 从后端 `catalog.en-US.json` 生成，产物入库，
`i18n:check` 断言它与后端文件一致。手写必然漂移，而漂移的表现是
"同一个任务类型在两个页面显示两个英文名"。

### D6 · 目录源常量一个字不改，一律走 overlay

**裁决**：`TASK_TYPES` / `TASK_MATERIALS` / `EVALUATION_DIMENSIONS` 的源行保持现状，
中文界面继续读它，英文界面读 overlay。

**理由**：这不是风格选择，是被测试卡口逼出来的唯一可行路径。
`test_task_type_parity.py` 的 `ENTRY_RE` 是**逐行匹配**（`for line in f`），
正则要求 `{ id: 'x', name: '中文'` 与 `stance_enum`、`score_dimensions` 在**同一行**、
且 `name` 是内联字面量。把 `name` 换成 `t('...')` 或把条目拆成多行，正则匹配 0 条，
而 `test_parser_actually_found_entries` 只要求 ≥10 条——测试会红。
（这次是可发现失败，属好事，但意味着这条路直接走不通。）

已验证的现状（`mock-data.ts:854`）：

```ts
{ id: 'concept_review', name: '概念评审', description: '核心循环、差异化、可行性', icon: '💡', category: 'development', IconComponent: Lightbulb, stance_enum: ['值得推进', '不值得', '观望'], score_dimensions: [...] },
```

**一行一条的书写格式本身是契约，禁止 reformat。**

### D7 · `report_lang` 存量行留 NULL，绝不回填

**分歧**：提案 B 说留 NULL（"不知道"）；提案 C 说回填 `zh-CN`（上线前是单语中文模板，可从代码史核验）。

**裁决**：留 NULL，不回填，无 DEFAULT。

**理由**：`report_lang` 记录的是"这次评审**请求**的产出语言"。历史行根本没有发生过这个请求——
回填 `zh-CN` 记录的是一个从未被声明过的值，是编造。
提案 C 的论证（"上线前不存在第二种可能"）成立的是"正文是中文"这件事，
而这两件事不是一回事：正文语言另有一个我们本期不打算造的字段。

本仓已经为完全同构的问题立过这条规矩（`db.py` 的 `key_source`）：
> 可空、无默认：老数据确实不知道当时花的是谁的钱，写成 X 会是编造……NULL 如实表达"不知道"。

**前端后果（强制）**：`report_lang === null` 必须渲染成"生成语言未记录"，
**不许当成 `zh-CN`**。`null` 分支和 `'zh-CN'` 分支是两个分支。

另：ORM 侧也不给 `default`，让"忘了写"表现为 NULL 而不是被默认值吞掉。

### D8 · 缺译标记：全仓统一 `⟦missing:<locale>:<key>⟧`

**分歧**：提案 A 用 `⟦key⟧`；提案 C 用 `[[i18n-missing:en-US:key]]`。

**裁决**：统一为 `⟦missing:<locale>:<key>⟧`，前后端**同形**。

```
⟦missing:en:page.history.count.total⟧
⟦missing:en-US:task_type.steam_page_review.name⟧
```

**理由**：统一形态的唯一目的是**一条断言覆盖全链路**——
`assert '⟦missing:' not in response_body`、一条 grep、一次截图肉眼可辨。
两种形态就要两条断言，而漏写第二条的那天缺译就恢复隐身。
`⟦`（U+27E6）/ `⟧`（U+27E7）在正常文案里绝不会出现。

行为：
- **DEV**：抛 `MissingMessageError`，红屏。不降级。
- **PROD**：渲染 `⟦missing:…⟧` + `console.error`。
- **永远禁止回落到另一种语言。** 回落 zh 会让"英文界面里混中文"变成看不出来的正常结果。

同一条规则用来修 `PersonaRadarChart.tsx:24,27` 的 `?? d.axis`：
查不到轴名时显示 `⟦missing:en:enum.behavior_axis.novelty_seeking⟧`，
而不是把后端英文键画在雷达图上假装那就是轴名。

### D9 · zh / en 比较的是**逻辑 key 集**，不是文件里的字面 key

三份提案里同时写着"zh/en key 集必须逐字相等"和"en 侧带 count 的 key 必须有 `_one`/`_other`"——
这两条是**互相矛盾**的，因为 en 侧的 `_one/_other` 会让字面 key 多于 zh 侧。
12 个 agent 会有 12 种绕法。

**裁决**：
- **逻辑 key** = 去掉复数后缀（`_zero` `_one` `_two` `_few` `_many` `_other`）后的 key。
- `i18n:check` 比较的是**逻辑 key 集**，必须逐字相等。
- 复数变体单独校验：`MessageVars` 里带 `count` 的 key，en 侧必须同时有 `_one` 和 `_other`，
  缺一个即非零退出。
- `t()` 的调用方**永远只写逻辑 key**，不写后缀。`MessageKey` 类型里也只有逻辑 key。

**变体解析顺序**（写进运行时注释，防被误读成"回落"）：
`key + '_' + Intl.PluralRules(locale).select(count)` → `key + '_other'` → `key`。
zh 只有 `other` 一个类别，所以 zh 侧写裸 key 即可。
**这是同一语言内的变体解析，不是跨语言回落，与 D8 不冲突。**

### D10 · 默认不合并语义相近的文案

**裁决**：同一句话出现在两个页面且措辞不同 → **两个 key**。措辞完全相同 → 才可**提案**移进 `common.*`，
那是一次有 owner、有 diff 的显式决定，不是抽 key 时的顺手合并。

**为什么**：盘点提出 severity 两套译名"需统一"，但代码里那两套是刻意不同的：
`Severity` 值域是 `critical/high/medium/low`（严重/高/中/低，见 `SeverityBadge.tsx:8-13`），
`EthicsSeverity` 只有三档（高危/中危/低危），而 `mock-data.ts:150-152` 的注释明写
"三档整体上移一档，因为 severity-low 是青色，在站内读起来像没问题，用在违规上会误导"。
合并会抹掉一个有记录的设计决定，而且值域根本不同。

同理：`AskPage` 与 `ReviewProgressPage` 的三条连接状态提示**默认各抽各的**
（`page.ask.*` 与 `page.progress.*`），两页的语气差异是刻意的。

**唯一例外见 D11。**

### D11 · 表单校验文案强制合并进 `common.validate.*`

**裁决**：客户端表单校验错误（"请输入邮箱" / "密码至少 8 位" / "两次输入不一致" / "此项必填"）
一律进 `common.validate.*`，由 batch-0 交付，页面 agent 只读不写。

**为什么这条是 D10 的例外**：这批文案在 5 个认证页 + 设置页 + 创建评审页里逐字重复，
它们不是"语气差异"，是同一条规则的同一句话。各抽各的会产生 7 份译文，
改一次校验规则要改 7 个地方，而且必然有一处忘改——那处的表现是
"同一个校验在不同页面说法不一样"，用户会以为是两种不同的错误。

**这也是三份提案都漏掉的一整类文案。**

### D12 · 语言状态不跟账号走

**裁决**：本期 `localStorage` 是 ui_lang 的唯一事实源，跨设备不同步。

**理由**：`users` 表没有任何 preferences / locale 列（`models/__init__.py:366-390`
全部列：id/email/password_hash/display_name/plan/is_active/is_guest/email_verified_at/
token_quota_total/created_at），跟账号走 = 加列 + 迁移 + 端点 + Identity 透出。
更重要的是它会引入一个新的静默失败面：登录瞬间语言被服务端值覆盖，
用户以为自己刚才的切换没生效。

匿名是本仓的一等形态（`optional_identity` + `user_id="anonymous"` 共享桶），
匿名用户根本没有行可存。

跨设备不同步是**可解释的行为**，而不是伪装成同步的不同步。
将来要做时的正确形态是"服务端值与本地不同时弹一次确认，不静默覆盖"。

### D13 · 富文本用自研 `Trans` + 具名 slot，单层不嵌套

**裁决**：`<terms>…</terms>` 具名 slot，slot 名由 codegen 变成类型，对不上是 tsc 错误。
限制单层不嵌套；`<br/>` 作为特殊 void slot 支持。消息串**永远不进 `innerHTML`**。

本仓 18 处内嵌全是一层，这个限制换来 tokenizer 保持 50 行、行为完全可预测。
需要嵌套时拆两条 key 或改设计，**不许靠 i18n 层解决**。

### D14 · WebSocket 侧后端不生成任何文案

**裁决**：进度事件保持稳定 `event` 名 + 结构化 `data`，前端出本地化文案并跟随 ui_lang 实时变化。

**理由**：进度是"此刻的界面状态"而不是产出物，用户在进度页切语言、下一条进度立刻变语言是正确行为。
而且 WS 握手根本没有干净的语言协商通道——浏览器 WebSocket API 不能带自定义 header，
本仓已经因此被迫让 token 走子协议（`websocket/__init__.py:75-79`）。

本期后端配套改动（P1，单 owner）：`review.failed` 的 `error` 从自由文本
改成 `{code, message, message_lang}`。现在推的是 `str(exc)`，即引擎/服务层的中文原文，前端翻不了。

---

## 3. key 命名规范

### 3.1 形状

```
<域>.<单元>.<块>.<角色>        恒 3 段或 4 段，不许 5 段
```

- **域**（第 1 段，闭集）：`common` | `nav` | `page` | `enum` | `catalog` | `error`
- **单元**（第 2 段）：页面名 / 枚举名 / 目录名。**文件名恒等于 `<域>.<单元>`。**
- **块**（第 3 段）：页面上的**结构块**（章节 / 卡片 / 表单组），不是 DOM 结构。
  改版换布局 key 不动。块名可用下划线复合：`consensus_empty`、`load_more`。
- **角色**（第 4 段，闭集，见 3.2）：这句话在界面上**扮演什么角色**，不是这句话的内容。
  改文案 key 不动。

3 段的情形是"这个块只有一句话"：`nav.item.home`、`enum.severity.critical`。

段名一律 `snake_case`。`enum.*` 那一层的叶子**直接用后端枚举值**，不做大小写转换。

### 3.2 角色白名单（闭集）

```
title  subtitle  desc  label  placeholder  hint  unit  value
cta  link  tab  step  badge
empty  loading  pending  success  error  confirm
aria  tooltip  meta
```

**这是闭集。** `scripts/i18n-gen.mjs` 会校验第 4 段属于这张表，不在表里直接非零退出。

为什么要闭集：不闭的话 12 个 agent 会写出 `btn` / `button` / `action` / `cta` 四种同义角色，
半年后没人能靠 key 猜到文案在哪。**要加新角色，改 `ROLES` 常量并跑 gen，由 batch-0 做，
页面 agent 不得自造。**

### 3.3 禁止事项

- **禁止把中文原文当 key**（source-as-key）。改一个字的文案就要改所有调用点，
  2000 个 key 会立刻不可维护。更致命的是本仓有一批中文串是 wire key
  （`TASK_MATERIALS[].key`）和引擎输入（`AskPage.tsx:954`），
  source-as-key 让"显示文案"和"协议字段"在文本层面无法区分。
- **禁止用序号做叶子**（`nav.item.item1`）。
- **禁止把样式信息写进 key**（`page.report.risk.red`）。

### 3.4 十个真实例子

| # | 原始位置与字符串 | key | 说明 |
|---|---|---|---|
| 1 | `Layout.tsx:9` `{ path: '/', label: '首页' }` | `nav.item.home` | 叶子用**路由语义名**，不用序号。3 段 |
| 2 | `Layout.tsx:428-433` 四态按钮（发送中/已发送/发送失败/重新发送） | `nav.verify_banner.sending` / `.success` / `.error` / `.cta` | **四态各一条 key，不是插值**。原来是嵌套三元，抽 key 时把三元保留在 tsx 里 |
| 3 | `ReviewHistoryPage.tsx:180` `` `已显示 ${loaded} 条` `` | `page.history.count.loaded_only` | 调用写 `t(k, { count: loaded })`，**不写 `_one/_other` 后缀**（D9） |
| 4 | `ReviewHistoryPage.tsx:183` `` `共 ${total} 条 · 已显示 ${loaded} 条` `` | `page.history.count.total_and_loaded` | 两个插值，plural 挂 `total`，`loaded` 当普通插值（ICU 也有这个限制） |
| 5 | `ReviewHistoryPage.tsx:184` `` `共 ${total} 条` `` | `page.history.count.total` | 3/4/5 是同一个三元的三个兄弟，**必须排在同一个 `count` 块下**才看得出它们是一组。注意还有第四个分支是空串（`total===null && loaded===0`）——**空串分支不进 key 表**，保持条件渲染 |
| 6 | `RegisterPage.tsx:120-128` 条款同意句 | `page.register.terms.consent` | 值：`注册即表示你同意<terms>服务条款</terms>与<privacy>隐私政策</privacy>`。**链接文字不拆出去**，否则英文语序改不了 |
| 7 | `ReportPage.tsx:247` `high: { label: '高风险', color: ..., bg: ... }` | `enum.release_risk.high` | **只有 `label` 进 key 表**，`color`/`bg`/`border` 留在 tsx——样式不是文案 |
| 8 | `ReportPage.tsx:371` `role_drift: '角色漂移（没有按这个人格的设定作答）'` | `enum.gate_reason.role_drift` | 叶子 = 后端枚举值原样。后端加新枚举而前端没跟上时显示 `⟦missing:…⟧` 而不是空白 |
| 9 | `SeverityBadge.tsx:9` `'严重'` 与 `mock-data.ts:154` `'高危'` | `enum.severity.critical` / `enum.ethics_severity.high` | **刻意不合并**（D10）：值域不同（4 档 vs 3 档），且 `mock-data.ts:150-152` 的注释记录了上移一档的设计决定 |
| 10 | `mock-data.ts:737` `{ key: '一句话pitch', label: '一句话介绍', placeholder: '用一句话描述…' }` | `catalog.material.concept_review.一句话pitch` → `{label, placeholder}` | overlay，**源行一字不改**（D6）。`key` 是 wire contract，**永不翻译**；只翻 `label`/`placeholder` |

---

## 4. 目录布局与并行分工

### 4.1 文件布局

```
web/frontend/src/i18n/
  runtime.ts            # t / Trans / MissingMessageError —— batch-0 独占，页面 agent 只读
  locale.ts             # ui_lang 单例 + localStorage + <html lang> + useLocale()
  format.ts             # formatDateTime / formatNumber / formatBytes / formatPercent / formatUsd
                        #   —— 全仓唯一允许调 toLocale* 的文件
  head.ts               # useDocumentTitle / setMetaDescription
  api-error.ts          # tApiError(e, fallbackKey)
  catalog.ts            # 目录 overlay 读取器（tCatalog / getMaterialField）
  types.ts              # Messages / MaterialOverlay 等形状类型
  keys.gen.ts           # 【生成物 · 禁止手改】MessageKey / RichMessageKey / MessageVars / MessageSlots
  locales/
    index.gen.ts        # 【生成物 · 禁止手改】per-locale 动态 import 表
    zh/
      common.ui.ts          common.action.ts      common.validate.ts    common.meta.ts
      enum.release_risk.ts  enum.severity.ts      enum.ethics_severity.ts
      enum.gate_reason.ts   enum.behavior_axis.ts enum.direction.ts     ...
      catalog.task_type.ts  catalog.material.ts   catalog.skill.ts
      catalog.persona_pack.ts  catalog.eval_dimension.ts  catalog.brand.ts
      error.api.ts          error.ws.ts
      nav.item.ts           nav.verify_banner.ts  nav.footer.ts
      page.report.ts        page.ask.ts           page.settings.ts      ...
    en/                 # 与 zh 同名文件一一对应，文件名对不上 = i18n:gen 失败
web/frontend/scripts/i18n-gen.mjs
web/frontend/src/pages/landing/landing-body.en.html   # 落地页唯一例外，见 4.4
```

**文件名规则：恒等于 key 的前两段。**
`page.history.count.total` → `page.history.ts`。`enum.severity.critical` → `enum.severity.ts`。

这条规则同时决定了三件事，所以它是整个并行方案的地基：
(a) 前两段决定文件、文件决定 owner，12 个 agent 天然不撞车；
(b) 不需要手写 barrel——手写 barrel 是 12 个 agent 唯一必然冲突的文件，所以它必须是生成物；
(c) 它顺带否掉了"一个文件装多个页面"的写法：
`page.legal.ts` 装 Terms + Privacy 会逼出 `page.legal.terms.section.title` 这种 5 段 key。
所以 **Terms 和 Privacy 是 `page.terms.ts` 和 `page.privacy.ts` 两个文件**（同一个 owner），
五个认证页同理拆成五个文件。

### 4.2 写权限清单（三份提案全都漏掉的一节）

**这是 12 个 agent 并行时最危险的空洞。** 提案里的分工表只分了 `page.*` 资源文件，
没有说 `components/` 和 `lib/` 归谁——而 `SeverityBadge.tsx` 被全站复用，
7 个页面 agent 会同时想去改它。

| 路径 | owner | 页面 agent 的权限 |
|---|---|---|
| `src/i18n/**` | batch-0 | 只读 |
| `scripts/i18n-gen.mjs` | batch-0 | 只读 |
| `src/components/**`（除 `Layout.tsx`） | batch-0 | **禁止编辑** |
| `src/components/Layout.tsx` | agent 12 | 禁止编辑 |
| `src/lib/**`（mock-data / api / apiClient / types / utils / ws） | batch-0 | **禁止编辑** |
| `src/store/**` | batch-0 | **禁止编辑** |
| `src/App.tsx` / `src/main.tsx` / `index.html` / `index.css` | batch-0 | **禁止编辑** |
| `eslint.config.js` / `package.json` / `tsconfig*.json` | batch-0 | **禁止编辑** |
| `src/pages/<你的页面>.tsx` | 对应 agent | 独占 |
| `src/i18n/locales/{zh,en}/<你的文件>.ts` | 对应 agent | 独占 |
| `src/temp/**` | 无 | **禁止编辑**（死代码） |
| 任何 `.py` / `web/backend/**` / `src/runner/**` | 后端 owner | **禁止编辑** |

在你负责的页面里发现共享文件需要改（比如 `SeverityBadge` 少一个 severity 档位）：
**写进你的交付报告，不要自己改。** batch-0 统一处理。

### 4.3 两批次

**batch-0（单 owner，必须先交付，其余人等它）**：

- `src/i18n/` 运行时本体 + `scripts/i18n-gen.mjs` + package.json scripts + eslint 规则
- `common.*`（`ui` / `action` / `validate` / `meta`）
- `enum.*`：`release_risk` / `evidence_quality` / `gate_reason` / `direction` / `disabled_reason` /
  `stop_reason` / `cross_exam_mode` / `severity` / `ethics_severity` / `behavior_axis` /
  `verdict` / `mode_badge` / `stance` / `rebuttal_status` / `calibration`
- `catalog.*`（含 `TASK_MATERIALS` 的 `as const` 化与 `getMaterialFields` 访问器）
- `error.api`（10 条）/ `error.ws`（5 个事件）
- `src/components/**`（除 Layout）、`src/lib/**`、`src/store/**`、`App.tsx`、`main.tsx`、`index.html`

**为什么必须串行这一段**：12 个页面 agent 都要读 `enum.*` / `catalog.*` / `common.*`。
不先行交付，他们会各自造一份，最后是 12 套枚举译名。
代价是串行一小段，换来的是页面 agent 之间**零共享文件**。

**batch-1（12 个页面 agent，全并行）**：

| agent | 负责的 .tsx | 负责的资源文件（zh + en 各一份） | 备注 |
|---|---|---|---|
| 1 | `ReportPage.tsx`（262 串） | `page.report.ts` | **含 `generateMarkdown():2672-2760` 的导出模板**——它不在 JSX 里，最容易漏 |
| 2 | `AskPage.tsx`（171 串） | `page.ask.ts` | **`:954` 与 `:798` 是 engine-prompt，保持中文发送，不进 key 表**（见 12.3） |
| 3 | `SettingsPage.tsx`（122 串） | `page.settings.ts` | 富文本密集：`:857` `<code>`、`:1119-1120` 双 `<strong>`、`:569-571` |
| 4 | `CreateReviewPage.tsx`（96 串） | `page.create.ts` | 提交路径 `:264-266` 把中文 key 当 `materials[].type` 发出，**一个字都不许动** |
| 5 | `TermsPage.tsx` + `PrivacyPage.tsx`（75+75） | `page.terms.ts` + `page.privacy.ts` | **英文译文标记为"待法务复核"，不随 `VITE_AL_LOCALES=zh,en` 直接上线** |
| 6 | `landing/LandingPage.tsx`（103 串） | `page.landing.ts` + `landing-body.en.html` | 见 4.4，**中文原件一个字不动** |
| 7 | `TutorialPage.tsx`（53 串） | `page.tutorial.ts` | 译文必须与 `catalog.material` **同源**，否则教程与实际表单对不上 |
| 8 | `PlansPage.tsx`（51 串） | `page.plans.ts` | **`:43,:45` mailto 正文不进 key 表**（收件人是站方，见 12.4） |
| 9 | `ReviewProgressPage.tsx`（48 串） | `page.progress.ts` | 三条连接提示**不与 `page.ask` 合并**（D10） |
| 10 | `ReviewHistoryPage.tsx` + `SharedReportPage.tsx` + `PersonasPage.tsx`（34+21+16） | `page.history.ts` + `page.shared.ts` + `page.personas.ts` | history 的分页三分支是全仓最典型的复数陷阱 |
| 11 | `LedgerPage.tsx` + `EvaluationPage.tsx` + `TaskTypesPage.tsx` + `SkillSelectPage.tsx`（56+32+25+12） | `page.ledger.ts` + `page.evaluation.ts` + `page.task_types.ts` + `page.skills.ts` | task_types/skills 的列表数据来自后端，页面只提供框架文案 |
| 12 | `Layout.tsx` + `LoginPage` + `RegisterPage` + `ForgotPasswordPage` + `ResetPasswordPage` + `VerifyEmailPage`（35+9+15+10+12+8） | `nav.item.ts` + `nav.verify_banner.ts` + `nav.footer.ts` + `page.login.ts` + `page.register.ts` + `page.forgot.ts` + `page.reset.ts` + `page.verify.ts` | 校验文案一律用 `common.validate.*`（D11），**不许各写各的** |

未列入任何 agent 的前端文件（`AmbientMotes.tsx`、`landing/HeroScene.tsx`、`src/temp/**`）：
零 UI 字符串，**不要碰**。`HeroScene.tsx` 的 128 个汉字全部在 GLSL 注释里，
按行统计的脚本会误报它。

### 4.4 落地页的特殊路线

`landing-body.html` 通过 `LandingPage.tsx:21` 的 `?raw` import + `:287` 的
`dangerouslySetInnerHTML` 整块注入。

**规定**：新增兄弟文件 `landing-body.en.html`，按 ui_lang 选 raw import。
**中文原件一个字不动。**

**为什么不能就地翻译**：`tests/test_landing_capability_claims.py:96-105` 在短语找不到时走
`pytest.skip` 而不是 fail。就地翻译会让 6 条"文案 ↔ 实现"断言**全部静默 skip 而测试全绿**——
防线形同虚设，正是纪律 2 点名的形态。
而且该文件 3804 个汉字里有 1994 个在 38 个 HTML 注释块内，属纪律 1 保护范围。

**agent 6 的额外交付物（不可省）**：为 `landing-body.en.html` 新写一套对应的英文断言测试。
不写的话英文版的能力声明就没人管了——这正是我们刚刚避免的那个洞，换个语言重新挖一遍。

另：`LandingPage.tsx:108` 的 `'帮我评审一下我的' + text` 是死代码
（`landing-body.html` 里已无 `class="chip"` 元素，`:31` 注释记录了 chips-examples 被砍掉）。
**本期不删也不翻，原样保留 + 加一行注释说明它已失效。**

---

## 5. 运行时 API

### 5.1 签名

```ts
// src/i18n/runtime.ts
import type { ReactNode } from 'react'
import type { MessageKey, RichMessageKey, MessageVars, MessageSlots } from './keys.gen'

type Empty = Record<string, never>

/** 漏传 count 是编译错误；key 写错是编译错误。 */
export function t<K extends MessageKey>(
  key: K,
  ...args: MessageVars[K] extends Empty ? [] : [vars: MessageVars[K]]
): string

export type SlotRender = (children: ReactNode) => ReactNode

/** slots 的键由消息串里的具名标签决定，少一个 / 多一个 / 拼错都是编译错误。 */
export function Trans<K extends RichMessageKey>(props: {
  k: K
  vars?: MessageVars[K]
  slots: { [S in MessageSlots[K]]: SlotRender }
}): ReactNode

/** 缺译文永不回落另一语言：DEV 抛错，PROD 返回 ⟦missing:…⟧ 并 console.error。 */
export class MissingMessageError extends Error {
  constructor(readonly key: string, readonly locale: Locale)
}
```

```ts
// src/i18n/locale.ts
export const LOCALES = (import.meta.env.VITE_AL_LOCALES ?? 'zh').split(',') as Locale[]
export type Locale = 'zh' | 'en'
export const DEFAULT_LOCALE: Locale = 'zh'
const HTML_LANG: Record<Locale, string> = { zh: 'zh-CN', en: 'en' }

// 真值放模块级：t() 必须能在 React 之外被调用
// （ReportPage.generateMarkdown 拼导出件 / api 层错误兜底 / document.title）。
// 只活在 hook 里的状态服务不了这三处，所以 zustand store 也不建——
// 直接 useSyncExternalStore(subscribe, getLocale) 就是 React 侧的全部所需。
let current: Locale = DEFAULT_LOCALE
const listeners = new Set<() => void>()

export function getLocale(): Locale
export function subscribe(fn: () => void): () => void

export async function setLocale(next: Locale): Promise<void>
/** React 视图。内部 useSyncExternalStore(subscribe, getLocale)。 */
export function useLocale(): Locale

/** 初始 ui_lang：?lang= > localStorage['al.locale'] > navigator.languages > zh。
 *  第三档映射不上时用 zh 且**不写回** localStorage —— 区分「用户选过」和「我们猜的」。 */
export function resolveInitialLocale(): Locale
export async function initI18n(): Promise<void>
```

`setLocale` 的行为规定（不许简化）：

```ts
export async function setLocale(next: Locale): Promise<void> {
  if (next === current) return
  await loadCatalog(next)              // 失败就抛，不静默停在旧语言
  current = next
  localStorage.setItem('al.locale', next)
  document.documentElement.lang = HTML_LANG[next]
  setMetaDescription(t('common.meta.description'))
  listeners.forEach((fn) => fn())
}
```

### 5.2 启动

```tsx
// src/main.tsx —— 语料先到位再渲染，t() 得以保持同步（无需 Suspense、无需 async t）
initI18n().then(
  () => createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>),
  // 语料加载失败：显示硬编码双语错误屏 + 重试按钮，绝不静默渲染另一种语言
  () => createRoot(document.getElementById('root')!).render(<I18nBootFailure />),
)
```

两份语料合计约 2000 条，全量静态打包会让中文用户白背一份英文。
做成 per-locale 动态 import 并在 `createRoot` 之前 await，Vite build 会自动注入
`modulepreload` 抵消额外往返。

**硬约束**：`ChunkErrorBoundary`（`App.tsx:28-53`）、`PageLoading`（`App.tsx:105-111`）
和 `I18nBootFailure` **必须硬编码双语字面量，不走 i18n**，并在文件里写明
"此处刻意不走 i18n"。否则 i18n 初始化失败时是白屏套白屏。
`ChunkErrorBoundary` 的注释已经为这条立过先例：
"Suspense 不捕获加载错误——发版后旧 chunk 404 会直接白屏，必须有边界兜底"。

### 5.3 资源文件写法

```ts
// src/i18n/locales/zh/page.history.ts   owner: agent-10
import type { Messages } from '@/i18n/types'

export default {
  'header.title':           '评审历史',
  'header.desc':            '你发起过的所有评审，点进去看报告或继续跟进',
  'count.loaded_only':      '已显示 {{count}} 条',
  'count.total_and_loaded': '共 {{total}} 条 · 已显示 {{loaded}} 条',
  'count.total':            '共 {{count}} 条',
  'load_more.cta':          '加载更多',
  'load_more.remaining':    '还有 {{count}} 条',
  'load_more.success':      '已加载全部 {{count}} 条评审',
  'list.empty':             '还没有评审',
  'item.confirm':           '确认删除？此操作不可撤销',
  'item.aria':              '删除评审「{{title}}」',
} satisfies Messages
```

```ts
// src/i18n/locales/en/page.history.ts   同一个 owner
export default {
  'header.title':           'Review history',
  'header.desc':            'Every review you started — open one for the report or to follow up',
  'count.loaded_only_one':      '{{count}} shown',
  'count.loaded_only_other':    '{{count}} shown',
  // 一句话里两个计数时，plural 只能挂一个（ICU 同限制）。这里挂 total。
  'count.total_and_loaded_one':   '{{total}} review · {{loaded}} shown',
  'count.total_and_loaded_other': '{{total}} reviews · {{loaded}} shown',
  'count.total_one':        '{{count}} review',
  'count.total_other':      '{{count}} reviews',
  'load_more.cta':          'Load more',
  'load_more.remaining_one':   '{{count}} more',
  'load_more.remaining_other': '{{count}} more',
  'load_more.success_one':  'All {{count}} review loaded',
  'load_more.success_other':'All {{count}} reviews loaded',
  'list.empty':             'No reviews yet',
  'item.confirm':           'Delete this review? This cannot be undone.',
  'item.aria':              'Delete review “{{title}}”',
} satisfies Messages
```

**用 `.ts` 不用 `.json` 的三个理由**：`satisfies Messages` 在编辑时就校验形状；
注释可以写"这条为什么不合并"的决策依据（本仓最看重的东西）；
`as const` 才能让 wire key 参与类型推导。要给翻译平台时导出 JSON 是 20 行脚本，反向不成立。

### 5.4 富文本

```tsx
// RegisterPage.tsx:120-128 改造后
<p className="mt-3 text-center text-xs leading-relaxed text-text-muted">
  <Trans
    k="page.register.terms.consent"
    slots={{
      terms:   (s) => <Link to="/terms"   className="mx-1 text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim">{s}</Link>,
      privacy: (s) => <Link to="/privacy" className="mx-1 text-brand-primary underline underline-offset-2 hover:text-brand-primary-dim">{s}</Link>,
    }}
  />
</p>
// zh: '注册即表示你同意<terms>服务条款</terms>与<privacy>隐私政策</privacy>'
// en: 'By signing up you agree to our <terms>Terms of Service</terms> and <privacy>Privacy Policy</privacy>'
```

tokenizer 只认 `<name>…</name>`（单层不嵌套）、`<br/>`、`{{var}}`，产出 `ReactNode[]`。

**注意 `RegisterPage.tsx:118-119` 那段注释**（"这两份文档写的都是本服务真实的边界……
值得被读到，而不是被一个'我已阅读'的勾选框代替"）**属纪律 1 保护范围，原样保留。**

### 5.5 目录 overlay 与 wire key 的编译期锁

```ts
// src/lib/mock-data.ts —— batch-0 唯一要动的一处标注
export const TASK_MATERIALS = {
  concept_review: [
    { key: '一句话pitch', label: '一句话介绍', placeholder: '用一句话描述你的游戏核心概念...', required: true },
    // …行首格式不变，parity 正则 `^  ([a-z_]+): \[` 不受影响
  ],
} as const

/** as const 后索引签名消失，两个消费点改走这里
 *  （CreateReviewPage.tsx:167 / TutorialPage.tsx:78）。 */
export function getMaterialFields(taskTypeId: string): readonly TaskMaterialField[] {
  return (TASK_MATERIALS as Record<string, readonly TaskMaterialField[]>)[taskTypeId] ?? []
}
```

```ts
// src/i18n/types.ts
export type MaterialOverlay = {
  [T in keyof typeof TASK_MATERIALS]: {
    // 内层键 = 中文 wire key 原文。改了 wire key，overlay 立刻 tsc 报错，
    // 不可能出现「编译通过 + 界面正常 + 引擎提取不到材料」的静默失败。
    [K in (typeof TASK_MATERIALS)[T][number]['key']]: { label: string; placeholder: string }
  }
}
```

这是对 critical 风险"中文 key 是 wire contract，批量替换会静默改掉它"的**编译期**正面卡口。
`TASK_MATERIALS` 现在标注为 `Record<string, TaskMaterialField[]>`（`mock-data.ts:736`），
key 的类型退化成 `string`，任何 overlay 都无法与它对齐——`as const` 是解开这个死结的唯一办法。
消费点只有两处且都是只读（`.map` / 索引读），readonly 化不破坏行为。

### 5.6 错误消息

```ts
// src/i18n/api-error.ts
/** zh：沿用后端 message（更具体）。非 zh：按 error.code 出前端译文，
 *  后端中文降级成 detail（折叠 / title 属性），绝不与英文界面混排。
 *  ⚠ 这是止血。10 个 code 撑不起后端 174 个 raise 点，真解在后端补细粒度 code。见 D2。 */
export function tApiError(e: unknown, fallbackKey: MessageKey): string
```

替换全站 30+ 处 `e instanceof Error ? e.message : '中文兜底'`。

---

## 6. 三份提案都漏掉的文案类型（逐类给规定）

这一节是本契约存在的主要理由之一。以下每一类在三份提案里都没有明确归属，
不写死就会变成 12 种写法。

### 6.1 瞬时消息 / Toast

**现状**：本仓**没有 Toast 组件**。所有"操作成功 / 操作失败"都是页面内的 error/success
state + 横幅。

**规定**：
- 沿用现状，**不许引入 Toast 库**（会带来 12 个 agent 各自的动画与位置）。
- key 用角色段 `success` / `error` / `pending`：`page.settings.key.success`。
- 后端错误一律经 `tApiError()`，不许直接 `t()` 一句自己编的中文。

### 6.2 表单校验错误

**规定**：见 D11。一律 `common.validate.*`，batch-0 交付，页面 agent 只读。

已知需要的（batch-0 必须交付全）：
`common.validate.required` / `.email_format` / `.password_min` / `.password_mismatch` /
`.too_long`（带 `{{max}}`）/ `.number_range`（带 `{{min}}` `{{max}}`）/ `.file_too_large`（带 `{{max}}`）。

### 6.3 浏览器标题（`document.title`）

**现状**：全站 `document.title` **零引用**，任何路由下标题都是 `index.html` 里那一串中文。

**规定**：
- 每个路由页面**必须**在顶层调用 `useDocumentTitle('page.<x>.meta.title')`。这是交付项，不是可选。
- 模板由 batch-0 提供：`common.meta.title_template` = `{{page}} · AudienceLens`，
  英文侧同形（品牌名不翻）。
- `index.html:7` 的静态中文 title **保持不动**——它是 JS 加载完成前的显示值，
  运行时由 `useDocumentTitle` 覆盖。

### 6.4 meta description

**现状**：`index.html` **根本没有 `<meta name="description">`**（只有 charset 和 viewport）。

**规定**：
- batch-0 在 `index.html` 补一条**静态中文** description（无 JS 时的诚实兜底）。
- `initI18n()` / `setLocale()` 时由 `setMetaDescription(t('common.meta.description'))` 更新。
- **必须在 `head.ts` 里写明**：这不是 SEO 方案。本站是纯客户端渲染，
  爬虫拿不到运行时改写的 meta。这里做的只是"分享链接预览时不要显示错的语言"，
  不要以为加了它 SEO 就有了。

### 6.5 日期 / 数字 / 字节 / 百分比 / 金额

**现状**：硬编码 `'zh-CN'` 三处（`ReviewHistoryPage.tsx:78`、`AskPage.tsx:86`、
`EvaluationPage.tsx:36`），无 locale 参数七处（`LedgerPage.tsx:270`、
`SettingsPage.tsx:635,1031,1047-1048`、`SharedReportPage.tsx:134`、`ReportPage.tsx:1251-1252`）。

**规定**：
- 全部改走 `@/i18n/format`。格式化必须与 `getLocale()` 同源——
  否则英文界面会出现中文日期，或者日期跟浏览器走、与界面语言脱钩。
- `format.ts` 是**全仓唯一**允许调 `toLocaleString` / `toLocaleDateString` /
  `toLocaleTimeString` / `Intl.*` 的文件，由 eslint 钉死：

```js
// eslint.config.js 追加（batch-0 做）
{
  files: ['src/**/*.{ts,tsx}'],
  ignores: ['src/i18n/format.ts'],
  rules: {
    'no-restricted-syntax': ['error', {
      selector: "CallExpression[callee.property.name=/^toLocale(String|DateString|TimeString)$/]",
      message: '日期/数字格式化走 @/i18n/format，硬编码 zh-CN 或省略 locale 会让格式与界面语言脱钩',
    }],
  },
}
```

- **金额不做货币换算。** `total_cost_usd` 恒为美元，`formatUsd()` 只改千分位与小数点，
  货币符号恒 `$`。换算需要汇率事实源，我们没有——猜一个汇率就是假数据。
- 排序如需 locale 感知，用 `format.ts` 导出的 `compareText(a, b)`（内部 `Intl.Collator`），
  不许各页自己 `localeCompare`。

### 6.6 空状态

**规定**：块名用 `<something>_empty` 或角色段 `empty`。
- 只有一句话 → `page.history.list.empty`
- 有标题 + 说明 + 按钮 → `page.history.list_empty.title` / `.desc` / `.cta`

**空状态必须有文案。** 禁止渲染空白 div——用户分不清"没有数据"和"加载失败"。

### 6.7 加载文案

**规定**：
- `App.tsx:105-111` 的 `PageLoading`（"正在加载…"）**保持硬编码双语，不走 i18n**（见 5.2）。
- 页面内的加载态用 `common.ui.loading` / `common.ui.submitting` / `common.ui.saving`
  （batch-0 交付），页面不自己写。
- 有具体语义的加载（"正在解析材料…"）才进 `page.*`，用角色段 `pending`。

### 6.8 二次确认对话框

**现状**：本仓**刻意不用 `window.confirm`**。`ReviewHistoryPage.tsx:143-149` 的注释记录了原因：
> 二次确认曾经用 window.confirm，实测不可靠：Chrome 在同一页面连弹几次后会给出
> "阻止此页面创建更多对话框"的勾选框，用户勾上之后 confirm() 直接静默返回 false，
> 于是点删除永远没反应、也没有任何报错——表现就是"删不掉"。

**规定**：
- **禁止引入 `window.confirm` / `alert` / `prompt`**。沿用页面内确认。
- 确认文案用角色段 `confirm`：`page.history.item.confirm`。
- **例外且必须单列**：删号二次确认短语（后端 `platform.py:747`
  `DELETE_CONFIRM_PHRASE = "删除我的账号"`）**不是文案，是凭据**。
  后端做的是中文字面量相等比较。前端 `SettingsPage` 里显示的那句提示可以翻译，
  但**用户要输入的那个短语必须原样显示中文**，且提示里要说明"请原样输入下面的中文"。
  否则英文用户永远删不掉账号，而且报错还是中文。
  这一条由 batch-0 交付为 `common.action.delete_account_phrase`，值恒为 `删除我的账号`，
  zh / en 两侧**字面相同**——这是全仓唯一一条 zh 与 en 必须字面相同的 key，
  文件里要写注释说明为什么。

### 6.9 无障碍标签

**规定**：`aria-label` / `title=`（tooltip）/ `placeholder` **全部进 key 表**，
分别用角色段 `aria` / `tooltip` / `placeholder`。

全仓 91 处，最多的是 `AskPage.tsx`（32 处）和 `SettingsPage.tsx`（10 处）。
盘点里 `aria-label` 常用「」包裹变量（如 `ReviewHistoryPage.tsx:251,328`）——
英文侧改成 `“…”`（U+201C/201D），不要留中文书名号。

**不要给纯装饰元素加 aria-label。** 本期不新增无障碍标注，只翻已有的。

### 6.10 404 与未知路由

**现状**：`App.tsx` 的 `*` 路由是 `<Navigate to="/" replace />`，没有 404 页面。
同文件对 `/pricing` 的注释已经吐槽过同类问题："否则它会被 * 兜底静默送回首页——用户以为自己点错了"。

**规定**：**本期不新增 404 页**（超范围）。禁止 agent 顺手加。
把它记进本文第 13 节的"已知欠债"，单独立项。

### 6.11 其余零散但必须点名的

| 类型 | 规定 |
|---|---|
| `console.log/warn/error` 的中文 | **不翻，不进 key 表**。开发者可见，不是 UI |
| 导出文件名（`generateMarkdown` 的 blob 下载名） | 保持现状不含中文；**但导出件正文必须带一行"本报告正文语言：X"**，见第 8.4 节 |
| 品牌专名（`types.ts:148-151`） | `Kimi` / `通义千问`→`Qwen` / `智谱 GLM`→`Zhipu GLM` 用**官方英文名**，不是直译。放 `catalog.brand.ts`。`'Ollama 本地模型'` 只有"本地模型"可译 |
| `PersonaRadarChart.tsx:91` 硬编码 `fontFamily: 'Noto Sans SC'` | batch-0 改成读 CSS 变量。英文界面上强制中文字体是明显的错 |
| RTL | **不在范围**。只有 zh/en，禁止加 `dir` 属性或 RTL 样式 |
| 英文文案变长撑破容器 | **记录，不修**。见 1.2 |

---

## 7. 类型安全与卡口

### 7.1 codegen，不用递归 `Paths<>` 推导

**理由**：递归 `Paths<typeof zh>` 在 2000 个 key、深度 4 的对象上会顶到 TS 递归上限
并显著拖慢 `tsc -b`，而 `tsc -b` 已经在 `build` 的关键路径上（`package.json:8`）。
更重要的是纯类型推导**只能保证 key 存在于 zh**，给不了这三条：
zh/en 逻辑 key 集相等、插值变量名一致、en 复数变体完整——
而这三条正是"缺译能被发现"的全部机制。类型推导只能防写错，防不了漏译。

```ts
// keys.gen.ts 产物形状（禁止手改）
export type MessageKey =
  | 'nav.item.home'
  | 'page.history.count.total'
  | 'page.register.terms.consent'
  | /* …约 2000 条 */
export type RichMessageKey = 'page.register.terms.consent' | /* …约 18 条带 slot 的 */
export interface MessageVars {
  'nav.item.home': Record<string, never>
  'page.history.count.total': { count: number }
  'page.history.count.total_and_loaded': { total: number; loaded: number }
}
export interface MessageSlots {
  'page.register.terms.consent': 'terms' | 'privacy'
}
```

**产物入库（committed）**，不每次构建现生成。这是刻意的：宁可多一次显式动作
（改完资源跑 `npm run i18n:gen`），也不要构建期现生成导致"本地过了 CI 没过"。
和本仓已有的 parity 测试风格一致——用一条会红的检查卡住漂移，而不是靠流程约束。

### 7.2 脚本与卡口

```jsonc
// web/frontend/package.json（batch-0 改）
"scripts": {
  "i18n:gen":          "node scripts/i18n-gen.mjs",
  "i18n:check":        "node scripts/i18n-gen.mjs --check",
  "i18n:sync-catalog": "node scripts/i18n-sync-catalog.mjs",
  "build":             "npm run i18n:check && tsc -b && vite build",
  "typecheck":         "npm run i18n:check && tsc -b --pretty false"
}
```

`--check` 非零退出的**七种**情形（缺一不可）：

1. zh / en 文件名集合不等。
2. 同一逻辑 key 在两侧的**插值变量名集合**不等（`{{count}}` vs `{{num}}`）。
3. 逻辑 key 集不等（去掉复数后缀后比较，见 D9）。
4. `MessageVars` 里带 `count` 的 key 在 en 侧缺 `_one` 或 `_other`。
5. key 的段数不是 3 或 4，或第 1 段不在域白名单，或第 4 段不在角色白名单（3.2）。
6. `keys.gen.ts` / `locales/index.gen.ts` 与目录现状不一致（有人改了资源没跑 gen）。
7. 资源文件里出现**禁止进 key 表**的内容（见 12 节的黑名单断言）。

### 7.3 每个 agent 提交前必须跑绿的四条

```bash
cd web/frontend && npm run i18n:check
cd web/frontend && npx tsc --noEmit          # 或 npm run typecheck
cd web/frontend && npm run build
cd web/backend  && python -m pytest -q
```

前端没有单测框架，所以卡口就是这四条，**一条都不许跳过**。

---

## 8. 语言到后端 / 评审语言冻结 / 旧报告

### 8.1 report_lang 走 body 显式字段，不从任何头推导

```python
# web/backend/app/api/platform.py:1401 CreateReviewRequest
    # 产出语言：显式请求参数，不读 Accept-Language。评审语言是产出物属性、
    # 要落库、要进提示词、要花真钱，不能由一个可被代理改写、可被浏览器自动填的
    # 协商头来决定。None = 用服务端默认；落库写的是**真实生效值**，不是 None。
    report_lang: Optional[str] = None
```

`Accept-Language` 是协商语义（"我偏好"），`report_lang` 是声明语义（"这次就用它"）。
传了不支持的值必须 **400**，不许静默回落成中文然后跑出一份用户没要的报告——
`persona_pack` 拼错静默回落 `game-core` 此前就是被当成 bug 修掉的
（`platform.py:1478-1481`，注释："用户选 A 包，跑的是 B 包"）。语言回落是同构问题。

校验位置：`_validate_artifact` 之后、`check_quota` 之前。理由同 artifact 校验——
语言不合法不该白占一次配额。

### 8.2 入队事务内冻结

```python
# review_service.py:49
def enqueue_review(review_id: str, *, api_key: str, key_source: str,
                   ..., report_lang: str) -> str:      # 关键字必填，不给默认值
    job_id = job_service.create_job(
        kind="review", ref_id=review_id, user_id=user_id,
        payload={"key_source": key_source, "report_lang": report_lang},
    )
```

同时写 `Review.report_lang` 与 `Job.payload['report_lang']`。
`_execute_review` **只读落库值**（`review.report_lang`），永不读请求上下文或用户当前偏好。

**竞态**：t0 用户以 en 发起（202 返回），t1 worker 开跑（几十秒到几分钟），
t2 用户在进度页切回 zh，t3 报告落库。执行期读偏好会出三种坏结果：
(a) t1 已发出的提示词改不了，t3 落库的语言标记与正文不符，元数据当场撒谎；
(b) `run_panel` 内人格是并发的，逐人格读偏好会产出中英混排的 `persona_notes`，
而 `similarity.py` 的中文极性词表在英文条目上**静默失效**，共识与分歧聚类直接算错且不报错；
(c) 进程重启收尸 / 重试时请求上下文早已消失，语言永远拿不回来——
而收尸逻辑本来就只能读落库的 `payload`（`db.py:132` 读 `job.payload["key_source"]` 判断该不该退钱）。

### 8.3 落库列与迁移

```python
# models/__init__.py — class Review，紧邻 mode / key_source
    # 这次评审**请求**的产出语言（BCP-47，如 "zh-CN"）。入队瞬间冻结，之后用户
    # 怎么切界面语言都不影响它。NULL = 本列上线前的历史行，语言未记录——是
    # 「不知道」，不是「中文」。同 key_source 的规矩，见 db.py:198-203。
    report_lang = Column(String, nullable=True)
```

```python
# db.py — _legacy_migrations() 内，紧跟 key_source 那段
    if "report_lang" not in columns:
        # 可空、无 DEFAULT、不回填。见 docs/I18N_CONTRACT.md D7。
        patches.append("ALTER TABLE reviews ADD COLUMN report_lang VARCHAR")
```

- 复用 `_legacy_migrations()`，靠 `inspect(engine).get_columns` 前置判断保证幂等，
  **不引入版本表**（另起一套迁移体系会产生第二个事实源）。
- 无 `DEFAULT`：本仓在 `db.py:182-196` 记过两遍 PG/SQLite 的 DDL 默认值坑
  （`DEFAULT false` vs `DEFAULT 0` 在 PostgreSQL boolean 上直接挂，而本机 SQLite 永远测不出）。
- 必须配一条"连跑两次 `_legacy_migrations()` 不报错、不改数据"的测试。

### 8.4 引擎打通与"不许只落库不进引擎"

`Review.report_lang` 列与把参数打通到 `run_panel` **必须同一批落地**，
并配一条断言 `Review.report_lang == report_json["meta"]["language"]` 的测试。

**为什么这条不能商量**：本仓亲口记录过这个失败形态（`src/runner/cli.py:768`）——
`mode` 加了列、落了库，却没进引擎，导致"快速扫一眼"实际跑的是全量流程，
人数和钱都没省，且全程不报错。语言重犯一次会更隐蔽：库里标 en、正文是 zh，
前端还会照着标记去渲染语言横幅，等于**系统主动撒谎**。

```python
# src/runner/aggregator.py — aggregate_report 的 meta（沿用 :587-588 立的规矩）
    if report_lang:
        meta["language"] = report_lang     # 取得到真值才写这个键
```

`meta` **只对新跑写**，历史 blob 不回填。

前端导出件（`ReportPage.generateMarkdown`）必须带一行：
`> 本报告正文语言：中文（生成于 …）` / `> Report body language: Chinese`。
导出的是文件，脱离界面之后没人知道它是什么语言。

### 8.5 读取侧与分享

```python
# platform.py get_review_v2 返回值新增
    "report_lang": review.report_lang,     # null = 未记录，前端不许当成 zh-CN

# share_service.py:73 to_public_dict 白名单新增
    "report_lang": review.report_lang,     # 访客据此显示语言横幅；不含身份/账单/材料
```

白名单的默认是"不给"，但语言标记不给的后果是**访客看到一份读不懂的报告而系统装作正常**。
它不是作者身份、不是账单、不是原始材料，公开它零风险。

分享链接**不带语言参数**：token 是对外唯一标识，加参数会让同一份报告出现多个 URL 形态，
而它们指向的正文完全一样。

### 8.6 旧报告：显示原文 + 显式横幅，不机翻、不自动重跑

```ts
export type ReportLangState =
  | { kind: 'match' }                          // 与 ui_lang 一致：不显示横幅
  | { kind: 'mismatch'; reportLang: string }   // "本报告以 X 生成，正文为原文"
  | { kind: 'unknown' }                        // report_lang === null："生成语言未记录"
```

**不机翻**：`report_json` 里的 `evidence[].quote` 是"来自你材料的原话"，
`validator.py:65-95` 靠逐 token 子串匹配校验过它确实出自材料——
翻译后的引文不再是原文任何一句，那是**伪造证据**。
而且机翻结果与模型原生产出在界面上无法区分，用户没有任何线索知道自己在读二手文本。
附带问题：`judgments.claim` 是判断复利的跨评审聚合键，翻译会让同一条判断在库里裂成两条。

**不自动重跑**：打开一份旧报告是只读动作，绝不能触发 `check_quota` 扣配额 + 真实 LLM 花费，
也不能覆盖属于用户资产的 `report_json`。重跑必须是显式点击、走正常 create 链路、
产生一条**新的** Review 行，旧行原样保留。

**分享页的横幅措辞必须与登录态不同，且不给"重跑"按钮**——访客没有配额、没有材料、无权重跑；
不给按钮就更必须给解释，否则访客会以为站点坏了。

---

## 9. 后端目录数据的双语存储与迁移

### 9.1 存储形态

```
web/backend/app/core/lang.py              语种定义与缺译标记（后端唯一）
web/backend/app/i18n/__init__.py          旁挂译文加载 + 应有 key 的机械推导
web/backend/app/i18n/catalog.en-US.json   任务类型/模式/技能/立场标签/人格档位的英文
```

```python
# web/backend/app/core/lang.py
Lang = Literal["zh-CN", "en-US"]
SUPPORTED_LANGS: tuple[Lang, ...] = ("zh-CN", "en-US")
DEFAULT_LANG: Lang = "zh-CN"
SUPPORTED_REPORT_LANGS: tuple[Lang, ...] = ("zh-CN",)   # 引擎侧英文链路就绪后再加

def missing_marker(key: str, lang: Lang) -> str:
    """缺译时返回它，绝不回落成另一种语言。
    形态与前端完全一致（见 docs/I18N_CONTRACT.md D8），
    这样一条 grep / 一条断言就能覆盖前后端。"""
    return f"⟦missing:{lang}:{key}⟧"
```

key 形状：`域.id.字段`。立场词用**中文原词**做后缀，因为它是稳定键：

```json
{
  "task_type.steam_page_review.name": "Steam Page Review",
  "task_type.steam_page_review.description": "Store-page IA, visual pitch, trust signals",
  "stance.steam_page_review.加愿望单": "Wishlist it",
  "review_mode.quick.description": "Fast triage, results within ~5 minutes",
  "skill.red_team_audience.name": "Red-team Audience"
}
```

### 9.2 序列化

```python
class TaskTypeResponse(BaseModel):
    task_type: str
    name_zh: str                  # 冻结：既有 wire 字段
    name_en: str                  # 新增；缺译是 ⟦missing:…⟧，不是 ""
    description: str              # 冻结（中文）
    description_en: str
    stance_enum: List[str]        # 冻结：wire key + 聚类键，永不翻译
    stance_labels_en: List[str]   # 与 stance_enum 同序等长
    score_dimensions: List[str]   # 本来就是英文键
```

**`stance_enum` 永久冻结为现有中文词。** 这个词同时是五处的聚类键
（`stance_distribution`、`compute_disagreements` 的 `stance_groups`、
`executive_summary.primary_recommendation`、HTML `stance_class`、`cli.py:676` 的兜底），
而 `output-schema.json` 对它**只校验 `minLength≥1`、没有 enum`**——
模型改说英文能顺利过 schema，然后共识与分歧统计静默打散、零报错。
显示层走 `stance_labels_en`，这是本仓前端已经用了十几处的"枚举→标签"模式。

### 9.3 迁移方式

**没有数据库迁移。** 目录不在库里——这是必须先纠正的前提：
26 张表没有一张是目录表，任务类型/模式/技能是 `services/__init__.py` 的 Python 字面量，
人格是 `src/personas/*.yaml`。所谓"迁移"就是：
1. 新增 `catalog.en-US.json`（纯新增文件）；
2. `get_task_types()` / `get_review_modes()` / `get_skill_types()` 的返回 dict 加同级键；
3. Pydantic 模型加兄弟字段。

三步都是**只加不改**，`name_zh` / `description` / `stance_enum` 字节不变，
所以三道现成 parity 卡口一条都不会红。

### 9.4 CI 断言

```python
def expected_catalog_keys() -> set[str]:
    """从 zh 事实源（services.TASK_TYPES / REVIEW_MODES / get_skill_types）
    机械推导出应有的全部 key，供 CI 做集合差集。"""
```

- `expected_catalog_keys() - catalog.en-US.json.keys()` 必须为空。
- 任意目录端点的响应体里不许出现 `⟦missing:`。

---

## 10. 引擎提示词与人格身份

> 本节是**已冻结的目标形态**，不是本期交付。本期只做 8.2–8.4 的管道打通。
> 写在这里是为了让"英文报告"这件事有一个不容二义的落点，避免后来的人重新发明一遍。

### 10.1 一份模板 + 参数，不开第二份模板

**禁止**：新建 `persona-prompt.en.md`。本仓刚删掉一处"与引擎平行的第二实现"
（`services/__init__.py:163-170` 记录了理由），`tests/test_persona_agent.py:169-179` 的
`TestTaskTableSingleSource` 存在的全部意义就是防"两套半口径"漂移。
而这份模板包含立场词表注入、评分骨架、`must_comment_on` 契约三处强耦合逻辑，
漂开的后果是模型按 A 打分、页面按 B 展示。

**禁止**：在提示词尾部加一句"用英文输出"。
提示词正文里摆着 `_minify_persona`（`persona_agent.py:266-268`）用
`yaml.dump(allow_unicode=True)` 铺开的**整张中文身份卡**，一句尾部指令对抗几百字中文上下文，
产出必然是中英混杂——而混杂是最难自动检出的失败形态。

**做法**：`run_panel` → `render_prompt` 贯穿 `output_lang` / `source_lang` 两个参数，
在模板里下发**逐字段语域契约**（五个语域各自说清）：

```
[LANGUAGE CONTRACT]
1. JSON 字段名、inference_level、severity、评分维度键：英文字面量，逐字照抄，永不翻译。
2. primary_stance：只能填给定枚举里的中文原词。它是聚类键不是显示文本——
   换个说法就会静默打散共识与分歧统计。
3. must_comment_on_check 的键：逐字照抄 PERSONA CARD 里的原文。
4. evidence[].source_quote：材料原文的逐字片段，语种 = 材料语种（source_lang），不翻译。
5. 其余散文（evidence[].content / key_issues.* / voice_sample / missing_information /
   meta.caveats）：跟 output_lang。
```

一句全局指令表达不了后四条，只会正好冲掉三个 wire key + 一个校验闸门的输入。

### 10.2 追问链路必须同批处理

`chat_service._build_prompt` 完全不复用评审提示词，且两个分支都**硬编码"简体中文"**
（`:88` 和 `:94`）。即使报告成功产出英文，用户点进任何一条追问回复仍是中文——
而追问是报告页最主要的二次交互。它必须与 10.1 同批落地。

### 10.3 人格身份**不**本地化 —— 这是结论，不是取舍

**张伟在英文模式下仍叫张伟。**

三条依据：

1. `region` 与 `age_range` 直接被 `_panel_audience_profiles`（`aggregator.py:357-383`）
   拼成报告的 `recruit_types`，而那段代码的注释明写它的口径是
   "取自人格档案的真实属性，可据此筛选同类真人受访者"。
   把"林岚 / 中国华东"改成"Emily / 北美"，报告就在向英文用户断言一个面板从未建模过的受众，
   **用户会照着去招募真人**。这是纪律 3 的假数据，也正是 `recruit_types` 那段注释当初写来防的事。
2. 本系统对外的核心保证是"身份不驱动判断"（提示词的 `[IDENTITY-BEHAVIOR DECOUPLING]` 段 +
   `counterfactual_identity.py` 的 payload 指纹审计）。
   若身份真的不驱动判断，改名买不到任何评审质量；若它驱动了，改名就是在**静默改变结论**。两条都指向不改。
3. 面板的真实构成就是中文市场加权的，显示英文名会让报告可信度**虚高**。

**允许本地化的只有"表述层"**：`archetype` / `identity_summary` / `motivations` /
`likes` / `dislikes` / `decision_rules` / `quit_triggers` / `continue_triggers` /
`first_scan_focus` / `review_output.*`，走 `src/personas/en-US/{pack}.yaml` overlay。

**overlay 禁止出现的键（靠一条测试机械卡死）**：
`id` `name` `gender` `age_range` `region` `language` `mbti` `model_hint` `task_affinity`
`behavior_profile` `gaming_profile`。
`behavior_profile` 的值是 `panel_selector.LEVEL` 的键（很低/低/中/高/很高），
翻了直接 `KeyError` 硬崩（`panel_selector.py:25-31` 的注释记录过这次崩溃）。

**真正该做的是把 `persona.language` 从死字段变成面板准入条件**：
人格 YAML 每条都已经带 `language`（29 条 `[zh-CN,en-US]`、10 条只有 `[zh-CN]`、
6 条只有 `[en-US]`），而 `select_panel` 从来不读它——这是一个和 `optional_personas`
（"写了三年从没人读"）同类的假旋钮。一个只读中文的人格去评英文商店页，结论本身就不可信。
接上它比编造英文名有价值得多，并且要在报告里如实列出被排除的人和原因
（`reason="language_mismatch"`），剔除后不足 `min_panel_size` **不静默补人**。

终局是另写一套面向英文市场的人格包（不是翻译）。
`audiencelens-v0.2-harness/personas/` 下那 3 个英文人格帮不上忙：
schema 都不一样（`behavioral_profile` vs `behavior_profile`）且**运行时从不读取**
（`review_service.py:110-114` 只认 `src/personas/`）。别把它当成"英文人设已现成"的依据。

### 10.3.1 overlay 的文件形状（补规定）

10.3 只规定了**哪些键**能进 overlay，没规定**文件长什么样**。结果是 batch-2 的三个
并行 agent 各写了一种外壳：裸的顶层 id mapping、`personas:` 包裹、`persona_overlays:`
包裹。三份内容都对，但加载器得同时认三种形状——这正是并行分片最典型的失败模式，
根因是契约留了空白而不是 agent 不守规矩。

**规范形状**（`src/personas/en-US/<与源同名>.yaml`）：

```yaml
version: '1.0'
locale: en-US
panel_id: game-core            # 必须与源文件的 panel_id 逐字相等
persona_overlays:              # mapping，键是人格 id
  P01-indie-core-operator:
    archetype: ...
    identity_summary: ...
```

两个决定的理由：

- **容器叫 `persona_overlays` 而不是 `personas`。** 源文件的 `personas:` 是**完整人格
  记录的列表**；overlay 里是以 id 为键的 mapping。同名不同形状是最容易看错的组合，
  改个名字就不会有人把两者当同一种东西读。
- **必须有 `panel_id` 且与源逐字相等。** 这是唯一能机械发现"overlay 抄串了包"的手段——
  内容全是英文散文，人眼看不出 family-casual 的 overlay 里混进了 mobile-f2p 的条目。

用 id 做 mapping 键是被 10.3 逼出来的：`id` 在禁翻键清单里，不能作为条目内的字段出现，
而合并又必须能定位到具体人格。

### 10.4 英文报告的前置硬门（一条没做完就不许开 `SUPPORTED_REPORT_LANGS`）

| # | 门 | 不做的后果 |
|---|---|---|
| 1 | `validate_evidence_grounding` 改判 `source_quote` 逐字命中 | 英文证据 + 中文材料 = 零命中 → `hallucination_risk=1.0` → 全员 `gated_out` → `AllPersonasFailedError`，而报错说的是"疑似幻觉"，与真因毫无关系 |
| 2 | 英文极性词表 + 英文 embedding 模型 | `price too high` 与 `price too low` 被合并进同一聚类——**正好把产品的核心价值（暴露分歧）算反**，且不报错 |
| 3 | `_IDENTITY_BEHAVIOR_PATTERN` 的英文版 | `compliance.ethics_score` 恒 100、`status` 恒"通过"——**伪装成通过的检查** |
| 4 | `ethics_service.STEREOTYPE_PATTERNS` 的英文版 | 同上，"零违规、满分通过"是最危险的假绿 |
| 5 | `REQUIRED_SECTIONS` 与 `report-template.md` 的失配先修好 | `report_structure` 这一维**今天就在给假分**；不修的话英文报告一评分会被归因成"英文质量差" |
| 6 | `chat_service` 的两处硬编码"简体中文" | 报告是英文、追问是中文 |

**禁止用放宽 `hallucination` 阈值绕过第 1 条**——那是把闸门关掉还假装它在。

---

## 11. 什么时候可以显式合并 / 拆分（给 agent 的判断树）

抽 key 时遇到"这句话别的页面好像也有"，按这棵树走，**不要自己权衡**：

1. 是表单校验错误吗？→ 用 `common.validate.*`（D11），结束。
2. 是加载 / 提交 / 保存 / 取消 / 确定这类通用动作词吗？→ 用 `common.ui.*` / `common.action.*`，结束。
3. 是枚举值的标签吗（键是后端枚举）？→ 用 `enum.*`，结束。
4. 两处措辞**逐字相同**吗？
   - 是 → **仍然各抽各的**，同时在你的交付报告里列出来，由 batch-0 决定要不要合并。
     你不能改别人的文件，所以你也不该替别人决定。
   - 否 → 各抽各的，结束。

**永远不要**因为"意思差不多"就合并。见 D10 的 severity 案例。

---

## 12. 禁止清单

### 12.1 纪律级（违反即为失败）

1. **不许翻译、删除、改写任何中文代码注释。** 全仓 1885 行中文注释记录了大量
   "为什么这么写"的决策依据，是这个仓库最有价值的部分。**一行都不许动。**
   只处理会渲染到界面上的字符串。
   > 判断方法：它出现在 `//` `/* */` `#` `<!-- -->` 里，或出现在 docstring 里 → 不动。
2. **不许静默兜底。** 禁止 `?? ''`、`?? '中文原文'`、`?? key`、`fallbackLng`。
   缺译必须表现为 DEV 抛错 / PROD `⟦missing:…⟧`。
3. **不许产生假数据。** 拿不准的英文译文**不许写占位符**（`TODO` / `[EN]` / 复制中文原文）。
   写出真实可上线的译文，把不确定的地方写进交付报告让人复核。
   资源文件里出现 `TODO` / `FIXME` / `xxx` / 与 zh 侧完全相同的中文字符串 → `i18n:check` 红。
4. **现有测试必须继续通过。**

### 12.2 绝对不能翻译的字符串（`i18n:check` 会断言它们不出现在任何资源文件里）

| 内容 | 位置 | 为什么 |
|---|---|---|
| `TASK_MATERIALS[].key` | `mock-data.ts:736-847` | 中文是 **wire contract**。`CreateReviewPage.tsx:264-266` 把它当 `materials[].type` 发给后端，后端 `MaterialExtractor.TASK_FIELDS` 按同样的中文字面量匹配。改了它 → 编译通过、界面正常、评审照跑 200，只是引擎再也提取不到材料 |
| `TASK_TYPES[].stance_enum` | `mock-data.ts:854+` | 后端 parity 测试逐字保护，且是引擎的聚类键 |
| `DELETE_CONFIRM_PHRASE` 的值 | 后端 `platform.py:747`，前端显示处 | 文案即凭据，见 6.8 |
| `AskPage.tsx:954` `就是${TASK_LABELS[candidate]}`、`:798` `（仅附图，无文字说明）` | AskPage | **engine-prompt**：会经 `api.parseIntent` 送进后端，而后端意图解析的启发式档是**中文关键词打分**。发英文 → 命中数归零 → 静默退化到默认任务类型，用户点了"Steam 商店页"却跑出概念评审，不报错 |
| `PlansPage.tsx:43,45` 的 mailto subject / body | PlansPage | 收件人是站方（solo dev），不是终端用户。翻了会让中文用户发出一封英文询价邮件 |
| `types.ts:148-150` 三个品牌专名 | types.ts | 用官方英文名，不是翻译。见 6.11 |
| `src/temp/**` 全部 | 4 个文件 371 行 | 死代码，`tsconfig.app.json:29` 已 exclude |
| `landing-body.html` 的原文 | 落地页 | 走兄弟文件，见 4.4 |

### 12.3 禁止的改法

- 禁止把 `TASK_TYPES` / `EVALUATION_DIMENSIONS` 的条目**拆成多行**或把 `name` 换成 `t()` 调用（D6）。
- 禁止在资源文件里写 JSX 或 HTML 标签（除 `Trans` 的具名 slot 和 `<br/>`）。
- 禁止 `dangerouslySetInnerHTML` 接消息串。
- 禁止引入 `window.confirm` / `alert` / `prompt`（6.8）。
- 禁止在页面里直接 `import` 另一个 agent 的资源文件绕过 `t()`。
- 禁止手改 `keys.gen.ts` / `locales/index.gen.ts`。
- 禁止编辑写权限清单（4.2）里不属于你的文件。
- 禁止顺手"优化"：不改布局、不改配色、不改组件结构、不删死代码、不加 404 页。
  本期只做 i18n，任何额外改动都会让 12 份 diff 无法 review。

---

## 13. 已知欠债（本期不做，但要记着）

1. 后端错误消息目录 + 细粒度 code + 两套信封收敛（D2）。
   在此之前英文用户的报错粒度就是 10 个码那么粗。
2. 404 页面（6.10）。`*` 路由静默跳首页，用户以为自己点错了。
3. 英文报告的六道前置硬门（10.4）。
4. 人格英文包（不是翻译，是另写一套面向英文市场的）。
5. `report_lang_actual`（实测产出语言）**故意不加**——"怎么判定实测语言"本身缺可信事实源，
   CJK 占比这类启发式会自己变成一个新的假数据来源。混排问题应该在引擎的输出校验闸门解决，不靠事后猜。
   将来有可信判定，再按"取得到真值才写这个键"的规矩补上。
6. `reviews.error_message` 里已经沉淀的系统中文（`db.py:56` 的收尸文案、
   `admin.py:1172` 的强制失败文案）。这批老行是既成事实，**只能标注不能修复**——
   任何迁移都不该去改写它。新写入的行应同时写稳定 `error_code`（本期不做）。
7. zh 侧仍有两份中文并存（`mock-data.ts` 的离线兜底 vs 后端目录），
   overlay 方案只在 en 侧根治漂移，中文侧继续靠现有 parity 测试守着。
   **这是接受既有债务，不是解决它。**
8. `harness/expected/*.yaml`（12 项）、`evaluation_service.REQUIRED_SECTIONS`（9 项）、
   `report-template.md` 的实际标题——三份"必需章节"定义互不相同，且第一份没有任何代码读它。
   要先定谁是事实源。

---

## 14. 交付物清单（每个 agent 自查）

- [ ] 我负责的 `.tsx` 里，**渲染到界面上的**中文字符串全部走 `t()` / `Trans`
- [ ] `zh/<我的文件>.ts` 与 `en/<我的文件>.ts` 都存在，逻辑 key 集相等
- [ ] en 侧带 `count` 的 key 都有 `_one` 和 `_other`
- [ ] 页面顶层调了 `useDocumentTitle('page.<x>.meta.title')`
- [ ] 所有 `aria-label` / `title=` / `placeholder` 进了 key 表
- [ ] 空状态、加载态、错误态、成功态都有文案
- [ ] 日期 / 数字 / 字节 / 百分比走 `@/i18n/format`，没有裸 `toLocale*`
- [ ] 校验文案用的是 `common.validate.*`，不是自己写的
- [ ] 没有碰写权限清单外的任何文件
- [ ] 没有改动任何中文注释
- [ ] 没有 `TODO` / 占位译文 / 与 zh 相同的中文串留在 en 资源里
- [ ] 四条命令全绿：`i18n:check` / `tsc --noEmit` / `build` / `pytest`
- [ ] 交付报告里列出了：拿不准的译文、发现但没改的共享文件问题、英文撑破容器的位置
