// frontend/src/services/api.js

import axios from "axios";

// 預設用相對路徑（同網域）：開發時由 Vite proxy 轉發到後端，
// 部署時由同一個站台提供 API。這樣從對外網域開啟也不會連錯機器。
// 需要指向別台後端時，才用 VITE_API_BASE_URL 覆寫。
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "";

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 120000,
  // 登入憑證改放 httpOnly cookie（JavaScript 讀不到，XSS 也偷不走），
  // 所以請求要帶上 cookie；不再自行附加 Authorization header。
  withCredentials: true,
});

// 說明：
// 帶著 token 卻收到 401，代表 token 已過期或失效，
// 清除登入狀態並導回登入頁。
// 訪客（未登入）收到 401 則交由各頁面自行顯示「需要登入」訊息。
// 因為讀不到 cookie，改以「本機是否記著使用者資料」判斷曾經登入。
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const wasLoggedIn = Boolean(localStorage.getItem("auth_user"));

    if (error.response?.status === 401 && wasLoggedIn) {
      localStorage.removeItem("auth_user");
      window.location.href = "/login";
    }

    return Promise.reject(error);
  }
);

export default api;
