// frontend/src/services/api.js

import axios from "axios";

// 預設用相對路徑（同網域）：開發時由 Vite proxy 轉發到後端，
// 部署時由同一個站台提供 API。這樣從對外網域開啟也不會連錯機器。
// 需要指向別台後端時，才用 VITE_API_BASE_URL 覆寫。
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "";

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 120000,
});

// 說明：
// 每個 request 自動帶上 JWT（如果已登入）。
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("auth_token");

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// 說明：
// 帶著 token 卻收到 401，代表 token 已過期或失效，
// 清除登入狀態並導回登入頁。
// 訪客（沒有 token）收到 401 則交由各頁面自行顯示「需要登入」訊息。
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const hasToken = Boolean(localStorage.getItem("auth_token"));

    if (error.response?.status === 401 && hasToken) {
      localStorage.removeItem("auth_token");
      localStorage.removeItem("auth_user");
      window.location.href = "/login";
    }

    return Promise.reject(error);
  }
);

export default api;
