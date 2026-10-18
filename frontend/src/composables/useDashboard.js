// frontend/src/composables/useDashboard.js

import { computed, reactive } from "vue";
import api from "../services/api.js";

export const DASHBOARD_ANALYSIS_CONTEXT_KEY = "dashboard-analysis-context";

export const TARGET_BOARDS = [
  { name: "facelift", label: "facelift 醫美/整形" },
  { name: "BeautySalon", label: "BeautySalon 保養" },
  { name: "MakeUp", label: "MakeUp 彩妝" },
  { name: "Mix_Match", label: "Mix_Match 穿搭" },
  { name: "fashion", label: "fashion 時尚" },
  { name: "Brand", label: "Brand 品牌/精品" },
  { name: "e-shopping", label: "e-shopping 網購" },
  { name: "NailSalon", label: "NailSalon 美甲" },
  { name: "Mancare", label: "Mancare 男性保養" },
  { name: "teeth_salon", label: "teeth_salon 牙齒美容" },
];

function readStoredAnalysisContext() {
  if (typeof localStorage === "undefined") return null;

  try {
    return JSON.parse(localStorage.getItem(DASHBOARD_ANALYSIS_CONTEXT_KEY) || "null");
  } catch {
    return null;
  }
}

const storedAnalysisContext = readStoredAnalysisContext();

// 剛登入或剛開啟頁面時不預設任何關鍵字，也不自動查詢，
// 等使用者自己輸入關鍵字並按下搜尋後才載入資料。
const state = reactive({
  keyword: "",
  selectedBoards: [],
  days: 30,
  sortBy: "push_count",
  analysisContextId: storedAnalysisContext?.id || "",

  dashboardData: null,
  insightData: null,

  // 使用者是否已經按過搜尋；尚未搜尋時 Dashboard 只顯示提示，不查詢任何資料。
  hasSearched: false,

  loadingDashboard: false,
  loadingInsight: false,
  loadingCrawler: false,

  errorMessage: "",

  // 所有平台的啟用看板（從後端取得），供平台篩選使用。
  availableBoards: [],
});

// 從後端取得各平台的看板清單（PTT / Dcard / Mobile01 / Threads）。
async function fetchAvailableBoards() {
  try {
    const response = await api.get("/api/dashboard/boards");
    state.availableBoards = response.data.data.boards || [];
  } catch (error) {
    console.error(error);
  }
}

function getSelectedBoards() {
  return state.selectedBoards.length
    ? state.selectedBoards
    : TARGET_BOARDS.map((board) => board.name);
}

function buildParams(extraParams = {}) {
  const params = new URLSearchParams();

  Object.entries(extraParams).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.append(key, value);
    }
  });

  state.selectedBoards.forEach((board) => {
    params.append("boards", board);
  });

  return params;
}

function publishDashboardAnalysisContext() {
  const context = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    keyword: state.keyword,
    days: state.days,
    boards: getSelectedBoards(),
    createdAt: new Date().toISOString(),
  };

  state.analysisContextId = context.id;
  localStorage.setItem(DASHBOARD_ANALYSIS_CONTEXT_KEY, JSON.stringify(context));

  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("dashboard-analysis-context-created", {
        detail: context,
      })
    );
  }

  return context;
}

// 清空 Dashboard 的查詢條件與結果（登入、登出、切換訪客時呼叫），
// 避免上一位使用者的查詢結果留在畫面上，也讓新登入的使用者從空白狀態開始。
export function resetDashboard() {
  state.keyword = "";
  state.selectedBoards = [];
  state.days = 30;
  state.sortBy = "push_count";
  state.dashboardData = null;
  state.insightData = null;
  state.hasSearched = false;
  state.errorMessage = "";
  state.analysisContextId = "";

  // 上一次搜尋留給 AI 問答的分析範圍也一併清除。
  try {
    localStorage.removeItem(DASHBOARD_ANALYSIS_CONTEXT_KEY);
  } catch {
    /* 無法存取 localStorage 時略過。 */
  }
}

export function useDashboard() {
  async function fetchDashboard() {
    state.loadingDashboard = true;
    state.errorMessage = "";

    try {
      const response = await api.get("/api/dashboard/full", {
        params: buildParams({
          keyword: state.keyword,
          days: state.days,
          sort_by: state.sortBy,
        }),
      });

      state.dashboardData = response.data.data;
    } catch (error) {
      console.error(error);
      state.errorMessage = "Dashboard API 載入失敗，請確認 backend 是否正在執行。";
    } finally {
      state.loadingDashboard = false;
    }
  }

  async function fetchInsight(forceRefresh = false) {
    state.loadingInsight = true;

    try {
      const response = await api.get("/api/analysis/keyword", {
        params: buildParams({
          keyword: state.keyword,
          analysis_type: "overview",
          days: state.days,
          force_refresh: forceRefresh,
        }),
      });

      state.insightData = response.data.result?.data || null;
    } catch (error) {
      console.error(error);
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

  async function searchDashboard(options = {}) {
    const { createConversation = true } = options;

    // 沒有關鍵字就不查詢，避免送出空白條件。
    if (!state.keyword.trim()) {
      state.errorMessage = "請先輸入至少一個關鍵字再搜尋。";
      return;
    }

    state.hasSearched = true;
    await fetchDashboard();

    if (createConversation) {
      publishDashboardAnalysisContext();
    }

    fetchInsight();
  }

  // 依平台篩選：傳入平台名稱就只看該平台，傳入空值代表全部平台。
  async function filterByPlatform(platform) {
    // 用「平台:看板」的形式，避免同名看板（PTT 與 Dcard 都有 facelift）混在一起。
    state.selectedBoards = platform
      ? state.availableBoards
          .filter((board) => board.platform === platform)
          .map((board) => `${board.platform}:${board.board}`)
      : [];

    // 尚未搜尋過時只記住平台選擇，等使用者按下搜尋再一起查詢。
    if (!state.hasSearched) return;

    await searchDashboard({ createConversation: false });
  }

  async function changeSort(sortBy) {
    state.sortBy = sortBy;
    if (!state.hasSearched) return;
    await fetchDashboard();
  }

  async function triggerCrawler() {
    state.loadingCrawler = true;
    state.errorMessage = "";

    try {
      await api.post("/api/crawler/ptt", null, {
        params: buildParams({ pages: 1 }),
      });
    } catch (error) {
      console.error(error);

      if (error.response?.status === 401) {
        state.errorMessage = "啟動爬蟲需要登入，請先登入系統。";
      } else if (error.response?.status === 409) {
        state.errorMessage = "已有爬取任務執行中，請稍候再試。";
      } else {
        state.errorMessage = "Crawler trigger failed. Please check backend status.";
      }
    } finally {
      state.loadingCrawler = false;
    }
  }

  async function exportArticles() {
    state.errorMessage = "";

    try {
      const response = await api.get("/api/export/articles.xlsx", {
        params: buildParams({
          keyword: state.keyword,
          days: state.days,
          sort_by: state.sortBy,
        }),
        responseType: "blob",
      });

      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement("a");

      link.href = url;
      link.download = `articles_${state.keyword}_${state.days}d.xlsx`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error(error);
      let detail = error.response?.data?.detail;
      // Axios returns error responses as blobs too for this download request.
      if (error.response?.data instanceof Blob && error.response.data.text) {
        try {
          detail = JSON.parse(await error.response.data.text()).detail;
        } catch { /* Use the status-specific message below. */ }
      }
      state.errorMessage = detail || (error.response?.status === 401
        ? "請先登入後匯出報表。"
        : error.response?.status === 403
          ? "目前方案未包含匯出功能，請升級方案。"
          : "Excel 匯出失敗，請稍後再試。");
    }
  }

  const overview = computed(() => state.dashboardData?.overview || {});
  const sentiment = computed(() => state.dashboardData?.sentiment || {});
  const trend = computed(() => state.dashboardData?.trend || []);
  const keywordTrends = computed(() => state.dashboardData?.keyword_trends || []);
  const hotArticles = computed(() => state.dashboardData?.hot_articles || []);
  const keywords = computed(() => state.dashboardData?.keywords || []);
  const dataStatus = computed(() => state.dashboardData?.data_status || {});
  const selectedBoards = computed(() => getSelectedBoards());

  return {
    state,
    overview,
    sentiment,
    trend,
    keywordTrends,
    hotArticles,
    keywords,
    dataStatus,
    targetBoards: TARGET_BOARDS,
    fetchAvailableBoards,
    filterByPlatform,
    selectedBoards,
    searchDashboard,
    fetchDashboard,
    fetchInsight,
    resetDashboard,
    changeSort,
    triggerCrawler,
    exportArticles,
  };
}
