<!-- frontend/src/views/DashboardView.vue -->

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

import SearchBar from "../components/SearchBar.vue";
import MetricsRow from "../components/MetricsRow.vue";
import DataStatusCard from "../components/DataStatusCard.vue";
import SentimentBar from "../components/SentimentBar.vue";
import TrendChart from "../components/TrendChart.vue";
import ArticleList from "../components/ArticleList.vue";
import InsightPanel from "../components/InsightPanel.vue";
import KeywordCloud from "../components/KeywordCloud.vue";
import TopicBars from "../components/TopicBars.vue";

import { useDashboard } from "../composables/useDashboard.js";
import { useWebSocket } from "../composables/useWebSocket.js";

const {
  state,
  overview,
  sentiment,
  trend,
  keywordTrends,
  hotArticles,
  keywords,
  dataStatus,
  searchDashboard,
  fetchDashboard,
  fetchInsight,
  changeSort,
} = useDashboard();

const {
  state: websocketState,
  connect,
} = useWebSocket();

const activeSection = ref("overview");

const dashboardSections = [
  { id: "overview", label: "總覽", icon: "▣" },
  { id: "crawler", label: "爬蟲管理", icon: "▤" },
  { id: "trend", label: "趨勢", icon: "▥" },
  { id: "sentiment", label: "情緒", icon: "◎" },
  { id: "articles", label: "熱門文章", icon: "♨" },
  { id: "insight", label: "洞察", icon: "✦" },
  { id: "keywords", label: "文字雲", icon: "☁" },
];

function updateActiveSection() {
  const sections = dashboardSections
    .map((section) => {
      const element = document.getElementById(`dashboard-${section.id}`);
      return {
        id: section.id,
        top: element ? element.getBoundingClientRect().top : Number.POSITIVE_INFINITY,
      };
    })
    .filter((section) => Number.isFinite(section.top));

  const current = sections
    .filter((section) => section.top <= 180)
    .sort((a, b) => b.top - a.top)[0] || sections.sort((a, b) => a.top - b.top)[0];

  if (current) {
    activeSection.value = current.id;
  }
}

function scrollToDashboardSection(sectionId) {
  const element = document.getElementById(`dashboard-${sectionId}`);

  if (!element) return;

  element.scrollIntoView({
    behavior: "smooth",
    block: "start",
  });
}

// 第一次開啟 Dashboard 時，自動載入預設關鍵字。
onMounted(() => {
  connect();
  searchDashboard({ createConversation: false });
  updateActiveSection();
  window.addEventListener("scroll", updateActiveSection, { passive: true });
  window.addEventListener("resize", updateActiveSection);
});

onBeforeUnmount(() => {
  window.removeEventListener("scroll", updateActiveSection);
  window.removeEventListener("resize", updateActiveSection);
});

watch(
  () => websocketState.statsVersion,
  () => {
    fetchDashboard();
  }
);
</script>

<template>
  <div class="dashboard-layout">
    <aside class="dashboard-sidebar" aria-label="Dashboard section navigation">
      <button
        v-for="section in dashboardSections"
        :key="section.id"
        class="dashboard-sidebar-item"
        :class="{ active: activeSection === section.id }"
        type="button"
        @click="scrollToDashboardSection(section.id)"
      >
        <span class="sidebar-icon">{{ section.icon }}</span>
        <span>{{ section.label }}</span>
      </button>
    </aside>

    <div class="dashboard-page">
      <div id="dashboard-overview" class="dashboard-section" data-dashboard-section>
        <SearchBar />

        <p v-if="state.errorMessage" class="error-message">
          {{ state.errorMessage }}
        </p>

        <div id="dashboard-crawler" data-dashboard-section>
          <DataStatusCard
            :status="dataStatus"
            :loading="state.loadingDashboard"
          />
        </div>

        <MetricsRow
          :overview="overview"
          :sentiment="sentiment"
          :loading="state.loadingDashboard"
        />
      </div>

      <div id="dashboard-trend" class="dashboard-section" data-dashboard-section>
        <TrendChart
          :trend="trend"
          :keyword-trends="keywordTrends"
          :keyword="state.keyword"
          :loading="state.loadingDashboard"
        />
      </div>

      <div id="dashboard-sentiment" class="dashboard-section dashboard-grid compact-insight-grid" data-dashboard-section>
        <SentimentBar
          :sentiment="sentiment"
          :loading="state.loadingDashboard"
        />

        <TopicBars
          :topics="keywords"
          :loading="state.loadingDashboard"
        />
      </div>

      <div id="dashboard-articles" class="dashboard-section" data-dashboard-section>
        <ArticleList
          :articles="hotArticles"
          :sort-by="state.sortBy"
          :loading="state.loadingDashboard"
          @change-sort="changeSort"
        />
      </div>

      <div id="dashboard-insight" class="dashboard-section" data-dashboard-section>
        <InsightPanel
          :insight="state.insightData"
          :loading="state.loadingInsight"
        />
      </div>

      <div id="dashboard-keywords" class="dashboard-section" data-dashboard-section>
        <KeywordCloud
          :keywords="keywords"
          :loading="state.loadingDashboard"
        />
      </div>
    </div>
  </div>
</template>
