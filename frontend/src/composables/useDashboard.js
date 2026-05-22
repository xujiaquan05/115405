// frontend/src/composables/useDashboard.js

import { computed, reactive } from "vue";
import api from "../services/api.js";

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

const state = reactive({
  keyword: "玻尿酸",
  selectedBoards: ["facelift", "BeautySalon", "MakeUp"],
  days: 30,
  sortBy: "push_count",

  dashboardData: null,
  insightData: null,

  loadingDashboard: false,
  loadingInsight: false,
  loadingCrawler: false,

  errorMessage: "",
});

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

  getSelectedBoards().forEach((board) => {
    params.append("boards", board);
  });

  return params;
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

  async function fetchInsight() {
    state.loadingInsight = true;

    try {
      const response = await api.get("/api/analysis/keyword", {
        params: buildParams({
          keyword: state.keyword,
          analysis_type: "overview",
          days: state.days,
          force_refresh: false,
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

  async function searchDashboard() {
    await fetchDashboard();
    fetchInsight();
  }

  async function changeSort(sortBy) {
    state.sortBy = sortBy;
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
      state.errorMessage = "Crawler trigger failed. Please check backend status.";
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
      state.errorMessage = "Excel export failed. Please try again later.";
    }
  }

  const overview = computed(() => state.dashboardData?.overview || {});
  const sentiment = computed(() => state.dashboardData?.sentiment || {});
  const trend = computed(() => state.dashboardData?.trend || []);
  const hotArticles = computed(() => state.dashboardData?.hot_articles || []);
  const keywords = computed(() => state.dashboardData?.keywords || []);
  const selectedBoards = computed(() => getSelectedBoards());

  return {
    state,
    overview,
    sentiment,
    trend,
    hotArticles,
    keywords,
    targetBoards: TARGET_BOARDS,
    selectedBoards,
    searchDashboard,
    fetchDashboard,
    fetchInsight,
    changeSort,
    triggerCrawler,
    exportArticles,
  };
}
