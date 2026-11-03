/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_USE_MOCK: string
  /** ICP 备案号；不设置则页脚与条款页不显示备案信息（见 src/lib/site.ts） */
  readonly VITE_ICP_TEXT?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
