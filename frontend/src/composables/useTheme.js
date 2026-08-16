// frontend/src/composables/useTheme.js

import { ref } from "vue";

const THEME_KEY = "theme";

// 目前主題（light / dark），從 localStorage 記憶。
const theme = ref(localStorage.getItem(THEME_KEY) || "light");

function applyTheme() {
  document.documentElement.setAttribute("data-theme", theme.value);
}

// 模組載入時立即套用，避免切頁時閃一下淺色。
applyTheme();

function toggleTheme() {
  theme.value = theme.value === "dark" ? "light" : "dark";
  localStorage.setItem(THEME_KEY, theme.value);
  applyTheme();
}

export function useTheme() {
  return { theme, toggleTheme };
}
