/**
 * 站点级、按部署而变的展示信息。都是**构建期**变量（Vite 在 build 时内联），
 * 改了要重新构建；Docker 部署通过 docker-compose.yml 的 build.args 传进来。
 */

/**
 * ICP 备案号，例如「京ICP备00000000号」。
 *
 * 只有在中国大陆提供服务的实例才需要，而且只能是**那个实例自己的**备案号——
 * 开源仓库里写死某一个号，等于让每个自建实例都挂着别人的备案。
 * 不设置时页脚和条款页都不渲染备案信息。
 * 工信部要求逐字符原样公示并链接到 beian.miit.gov.cn，所以这里不做任何改写，
 * 也不进 i18n 语料。
 */
export const ICP_TEXT: string = ((import.meta.env.VITE_ICP_TEXT as string | undefined) ?? '').trim()
