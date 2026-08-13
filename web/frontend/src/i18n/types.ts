/**
 * i18n 内核的形状类型。
 *
 * 这里刻意只有「形状」，没有 key 联合类型——后者在 keys.gen.ts，是生成物。
 * 分开的理由：资源文件（locales/**）要 import 本文件做 `satisfies Messages`，
 * 而 keys.gen.ts 是由资源文件反推出来的。合在一起会形成
 * 「资源文件 import 由资源文件生成的东西」的循环，第一次生成时根本跑不起来。
 */

/**
 * 一个资源文件的形状：扁平的 `块.角色 → 文案` 表。
 *
 * 注意这里的 key **不含前两段**。完整 key = `<文件名去掉 .ts>.<这里的 key>`，
 * 例如 locales/zh/page.history.ts 里的 'count.total' → 'page.history.count.total'。
 * 这条规则不是约定俗成，是 i18n-gen.mjs 唯一的拼接规则，也是
 * 「文件名决定 owner、12 个 agent 天然不撞车」的实现基础（契约 4.1）。
 *
 * 值里允许的占位符只有两种：
 *   {{name}}          —— 插值
 *   <slot>…</slot>    —— 具名富文本槽（只有 Trans 认，单层不嵌套，见契约 D13）
 *   <br/>             —— 特殊 void slot
 */
export type Messages = Record<string, string>

/** t() / Trans() 接受的插值实参。数字走 count 复数分支，其余原样字符串化。 */
export type MessageVarValue = string | number

/**
 * 一个 locale 的完整语料：完整 key（含全部段）→ 文案。
 * 由 locales/<locale>/index.gen.ts 在构建期拼好，运行时只读。
 */
export type Catalog = Record<string, string>
