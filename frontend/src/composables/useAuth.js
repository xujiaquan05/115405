// frontend/src/composables/useAuth.js

import { computed, reactive } from "vue";
import api from "../services/api";

// 說明：
// 登入憑證放在 httpOnly cookie（由後端設定），JavaScript 讀不到，
// 因此前端只保留「使用者資訊」用來顯示畫面與判斷是否已登入；
// 重新整理頁面後仍保持登入狀態，靠的是 cookie 而不是 localStorage。
// 訪客模式只設一個旗標。
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
  user: readStoredUser(),
  guest: localStorage.getItem(GUEST_KEY) === "1",
  loading: false,
  errorMessage: "",
});

// 讀不到 cookie，所以以「有沒有使用者資料」代表已登入；
// cookie 若已失效，下一個 API 請求會回 401 並由攔截器導回登入頁。
const isAuthenticated = computed(() => Boolean(state.user));
const isGuest = computed(() => !state.user && state.guest);

async function login(username, password) {
  state.loading = true;
  state.errorMessage = "";

  try {
    const response = await api.post("/api/auth/login", { username, password });

    // 刻意不保存 access_token：憑證已在 httpOnly cookie 裡。
    state.user = response.data.user;
    state.guest = false;

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
  state.user = null;

  localStorage.setItem(GUEST_KEY, "1");
  localStorage.removeItem(USER_KEY);
}

async function logout() {
  // cookie 是 httpOnly，前端刪不掉，必須請後端回 Set-Cookie 清除。
  try {
    await api.post("/api/auth/logout");
  } catch (error) {
    console.error(error);
  }

  state.user = null;
  state.guest = false;

  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(GUEST_KEY);
}

// 用新的使用者資料覆蓋（例如改了顯示名稱、或重新抓 /me），
// 同步更新 localStorage，讓 Navbar 等其他畫面也跟著變。
function updateUser(nextUser) {
  if (!nextUser) return;

  state.user = { ...(state.user || {}), ...nextUser };
  localStorage.setItem(USER_KEY, JSON.stringify(state.user));
}

export function useAuth() {
  return {
    state,
    isAuthenticated,
    isGuest,
    login,
    logout,
    enterGuestMode,
    updateUser,
  };
}
