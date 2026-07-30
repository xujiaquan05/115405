// frontend/src/composables/useAlerts.js

import { reactive } from "vue";
import api from "../services/api";

// 全域共用的未讀預警數，讓 navbar 徽章與監控頁同步。
const state = reactive({
  unreadCount: 0,
});

async function fetchUnread() {
  try {
    const response = await api.get("/api/monitor/alerts", { params: { limit: 1 } });
    state.unreadCount = response.data.data.unread_count || 0;
  } catch (error) {
    // 靜默失敗，不影響其他頁面。
    console.error(error);
  }
}

export function useAlerts() {
  return { state, fetchUnread };
}
