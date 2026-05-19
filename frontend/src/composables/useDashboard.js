// frontend/src/composables/useDashboard.js

import { reactive, computed } from "vue";
import api from "../services/api.js";


// Note:
// Đây là state dùng chung cho toàn bộ Dashboard.
// Vì đặt bên ngoài function useDashboard(),
// nên SearchBar.vue và DashboardView.vue sẽ dùng chung cùng một dữ liệu.
const state = reactive({
  keyword: "玻尿酸",
  board: "all",
  days: 30,
  sortBy: "push_count",

  dashboardData: null,
  insightData: null,

  loadingDashboard: false,
  loadingInsight: false,

  errorMessage: "",
});


export function useDashboard() {
  async function fetchDashboard() {
    /*
      Note:
      Hàm này gọi API Phase 3:
      GET /api/dashboard/full

      API này trả về:
      - overview
      - sentiment
      - trend
      - hot_articles
      - keywords
    */

    state.loadingDashboard = true;
    state.errorMessage = "";

    try {
      const response = await api.get("/api/dashboard/full", {
        params: {
          keyword: state.keyword,
          days: state.days,
          sort_by: state.sortBy,
        },
      });

      // Note:
      // Backend trả dữ liệu chính trong response.data.data.
      state.dashboardData = response.data.data;
    } catch (error) {
      console.error(error);

      // Note:
      // Nếu backend chưa chạy hoặc API lỗi, hiện thông báo trên Dashboard.
      state.errorMessage = "Dashboard API 載入失敗，請確認 backend 是否正在執行。";
    } finally {
      state.loadingDashboard = false;
    }
  }


  async function fetchInsight() {
    /*
      Note:
      Hàm này gọi API Phase 4:
      GET /api/analysis/keyword

      API này dùng Gemini để tạo LLM insight.
      Nếu Gemini hết quota, Dashboard vẫn phải chạy bình thường.
    */

    state.loadingInsight = true;

    try {
      const response = await api.get("/api/analysis/keyword", {
        params: {
          keyword: state.keyword,
          analysis_type: "overview",
          days: state.days,
          force_refresh: false,
        },
      });

      state.insightData = response.data.result?.data || null;
    } catch (error) {
      console.error(error);

      // Note:
      // Insight là phần phụ trợ, nên nếu lỗi thì không làm hỏng toàn bộ Dashboard.
      state.insightData = {
        summary: "LLM 洞察載入失敗，可能是 Gemini API quota 不足或 backend 尚未啟動。",
        hot_topics: [],
        consumer_pain_points: [],
        marketing_suggestions: [],
      };
    } finally {
      state.loadingInsight = false;
    }
  }


  async function searchDashboard() {
    /*
      Note:
      Hàm này được gọi khi user bấm nút 搜尋.

      Mình cho Dashboard load trước,
      sau đó mới gọi LLM insight.
      Vì Gemini có thể chậm hoặc hết quota,
      không nên để nó chặn toàn bộ Dashboard.
    */

    await fetchDashboard();
    fetchInsight();
  }


  async function changeSort(sortBy) {
    /*
      Note:
      Khi user đổi排序方式:
      - push_count
      - latest
      - relevance

      Thì chỉ cần gọi lại Dashboard API.
    */

    state.sortBy = sortBy;
    await fetchDashboard();
  }


  // Note:
  // computed giúp component không bị lỗi khi dashboardData vẫn đang là null.
  const overview = computed(() => state.dashboardData?.overview || {});
  const sentiment = computed(() => state.dashboardData?.sentiment || {});
  const trend = computed(() => state.dashboardData?.trend || []);
  const hotArticles = computed(() => state.dashboardData?.hot_articles || []);
  const keywords = computed(() => state.dashboardData?.keywords || []);

  return {
    state,
    overview,
    sentiment,
    trend,
    hotArticles,
    keywords,
    searchDashboard,
    fetchDashboard,
    fetchInsight,
    changeSort,
  };
}