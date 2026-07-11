// frontend/src/composables/useAuth.js

import { computed, reactive } from "vue";
import api from "../services/api";

// 說明：
// token 與使用者資訊存在 localStorage，
// 重新整理頁面後仍保持登入狀態。
// 訪客模式只設一個旗標，不發 token。
const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";
const GUEST_KEY = "auth_guest";

function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

const state = reactive({
  token: localStorage.getItem(TOKEN_KEY) || "",
  user: readStoredUser(),
  guest: localStorage.getItem(GUEST_KEY) === "1",
  loading: false,
  errorMessage: "",
});

const isAuthenticated = computed(() => Boolean(state.token));
const isGuest = computed(() => !state.token && state.guest);

async function login(username, password) {
  state.loading = true;
  state.errorMessage = "";

  try {
    const response = await api.post("/api/auth/login", { username, password });

    state.token = response.data.access_token;
    state.user = response.data.user;
    state.guest = false;

    localStorage.setItem(TOKEN_KEY, state.token);
    localStorage.setItem(USER_KEY, JSON.stringify(state.user));
    localStorage.removeItem(GUEST_KEY);

    return true;
  } catch (error) {
    console.error(error);

    if (error.response?.status === 429) {
      state.errorMessage = "嘗試次數過多，請稍後再試。";
    } else if (error.response?.status === 401) {
      state.errorMessage = error.response?.data?.detail || "帳號或密碼錯誤，請重新輸入。";
    } else {
      state.errorMessage = "登入失敗，請確認網路或 backend 狀態。";
    }

    return false;
  } finally {
    state.loading = false;
  }
}

function enterGuestMode() {
  state.guest = true;
  state.token = "";
  state.user = null;

  localStorage.setItem(GUEST_KEY, "1");
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function logout() {
  state.token = "";
  state.user = null;
  state.guest = false;

  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(GUEST_KEY);
}

export function useAuth() {
  return {
    state,
    isAuthenticated,
    isGuest,
    login,
    logout,
    enterGuestMode,
  };
}
