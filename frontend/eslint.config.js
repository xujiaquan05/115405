// frontend/eslint.config.js

import js from "@eslint/js";
import pluginVue from "eslint-plugin-vue";
import globals from "globals";

// 後端有 ruff 在 CI 把關（已抓到兩個真實錯誤），前端原本什麼都沒有。
// 這份設定的目標是「抓真正的錯」而不是統一排版風格：
// 未定義的變數、沒用到的變數、Vue 樣板寫錯等。
export default [
  { ignores: ["dist/**", "node_modules/**"] },

  js.configs.recommended,
  ...pluginVue.configs["flat/recommended"],

  {
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        ...globals.browser,
        // Vitest 的全域函式（vitest.config 開了 globals: true）。
        describe: "readonly",
        it: "readonly",
        expect: "readonly",
        vi: "readonly",
        beforeEach: "readonly",
        afterEach: "readonly",
      },
    },
    rules: {
      // 元件名稱用單字（DashboardView、SearchBar）是本專案既有慣例，
      // 為了這條規則改掉所有檔名沒有實質好處。
      "vue/multi-word-component-names": "off",
      // 樣板的排版交給人判斷，這裡只關心會出錯的東西。
      "vue/max-attributes-per-line": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/html-self-closing": "off",
      "vue/html-indent": "off",
      "vue/html-closing-bracket-newline": "off",
      "vue/attributes-order": "off",
      // 全形空白（U+3000）在中文介面文字中是正確用法，
      // 例如「正面 12%　中性 60%」用它分隔標籤，不該被當成錯誤。
      "no-irregular-whitespace": "off",
      // 樣板文字換行與否交給人判斷。
      "vue/multiline-html-element-content-newline": "off",
      // 有意忽略的參數以底線開頭，例如 catch (_error)。
      "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
];
