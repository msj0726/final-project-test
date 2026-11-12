import js from '@eslint/js'
import { defineConfig, globalIgnores } from 'eslint/config'
import vue from 'eslint-plugin-vue'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default defineConfig([
  globalIgnores(['dist', 'node_modules', 'playwright-report', 'test-results', 'public']),
  js.configs.recommended,
  tseslint.configs.recommended,
  vue.configs['flat/essential'],
  {
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
  },
  {
    files: ['src/**/*.{ts,vue}'],
    languageOptions: { globals: globals.browser },
    rules: {
      // 화면 컴포넌트는 route 단위 한 단어 이름(Page)을 쓰므로 다중 단어 규칙은 끈다
      'vue/multi-word-component-names': 'off',
      // 외부에서 오는 값은 unknown 으로 받고 좁혀 쓴다
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-console': ['error', { allow: ['warn', 'error'] }],
      eqeqeq: ['error', 'always', { null: 'ignore' }],
    },
  },
  {
    files: ['e2e/**/*.ts', 'playwright.config.ts', 'vite.config.ts', 'eslint.config.js'],
    languageOptions: { globals: globals.node },
  },
])
