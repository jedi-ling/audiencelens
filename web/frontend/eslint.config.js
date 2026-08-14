import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  {
    // 日期/数字/字节/百分比/金额的格式化必须与 getLocale() 同源。
    // 硬编码 'zh-CN' 会让英文界面显示中文日期；省略 locale 参数会让日期跟浏览器
    // 走、与界面语言脱钩（用户把界面切成英文，日期还是中文格式，且没人能解释）。
    // 现状里两种都有：硬编码三处、省略七处，见 docs/I18N_CONTRACT.md 6.5。
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/i18n/format.ts', 'src/temp/**'],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector:
            "CallExpression[callee.property.name=/^toLocale(String|DateString|TimeString)$/]",
          message:
            '日期/数字格式化走 @/i18n/format，硬编码 zh-CN 或省略 locale 会让格式与界面语言脱钩',
        },
      ],
    },
  },
])
