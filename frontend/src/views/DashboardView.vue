<!-- frontend/src/views/DashboardView.vue -->

<script setup>
import { onMounted, watch } from "vue";

import SearchBar from "../components/SearchBar.vue";
import MetricsRow from "../components/MetricsRow.vue";
import SentimentBar from "../components/SentimentBar.vue";
import TrendChart from "../components/TrendChart.vue";
import ArticleList from "../components/ArticleList.vue";
import InsightPanel from "../components/InsightPanel.vue";
import KeywordCloud from "../components/KeywordCloud.vue";

import { useDashboard } from "../composables/useDashboard.js";
import { useWebSocket } from "../composables/useWebSocket.js";

const {
  state,
  overview,
  sentiment,
  trend,
  hotArticles,
  keywords,
  searchDashboard,
  fetchDashboard,
  changeSort,
} = useDashboard();

const {
  state: websocketState,
  connect,
} = useWebSocket();


// Note:
// Khi mở Dashboard lần đầu, tự động load keyword mặc định.
onMounted(() => {
  connect();
  searchDashboard();
});

watch(
  () => websocketState.statsVersion,
  () => {
    fetchDashboard();
  }
);
</script>

<template>
  <div class="dashboard-page">
    <SearchBar />

    <section class="realtime-panel">
      <div class="realtime-header">
        <span
          class="connection-dot"
          :class="{ online: websocketState.connected }"
        ></span>
        <strong>
          {{ websocketState.connected ? "Realtime connected" : "Realtime offline" }}
        </strong>
        <span v-if="websocketState.reconnecting" class="realtime-muted">
          reconnecting...
        </span>
      </div>

      <div
        v-if="websocketState.crawler.status !== 'idle'"
        class="crawler-progress"
      >
        <div class="progress-text">
          <span>
            {{ websocketState.crawler.board || "Crawler" }}
            page {{ websocketState.crawler.currentPage }}/{{ websocketState.crawler.totalPages }}
          </span>
          <span>{{ websocketState.crawler.progress }}%</span>
        </div>
        <div class="progress-track">
          <div
            class="progress-fill"
            :style="{ width: `${websocketState.crawler.progress}%` }"
          ></div>
        </div>
        <p class="realtime-muted">
          Crawled {{ websocketState.crawler.crawledCount }} articles.
          New {{ websocketState.crawler.newCount }},
          skipped {{ websocketState.crawler.skippedCount }}.
        </p>
      </div>

      <div
        v-if="websocketState.notifications.length"
        class="notification-list"
      >
        <div
          v-for="notification in websocketState.notifications"
          :key="notification.id"
          class="notification-item"
          :class="notification.type"
        >
          <span>{{ notification.message }}</span>
          <small>{{ notification.createdAt }}</small>
        </div>
      </div>
    </section>

    <p v-if="state.errorMessage" class="error-message">
      {{ state.errorMessage }}
    </p>

    <MetricsRow
      :overview="overview"
      :sentiment="sentiment"
      :loading="state.loadingDashboard"
    />

    <div class="dashboard-grid">
      <TrendChart
        :trend="trend"
        :loading="state.loadingDashboard"
      />

      <SentimentBar
        :sentiment="sentiment"
        :loading="state.loadingDashboard"
      />
    </div>

    <div class="dashboard-grid">
      <ArticleList
        :articles="hotArticles"
        :sort-by="state.sortBy"
        :loading="state.loadingDashboard"
        @change-sort="changeSort"
      />

      <div class="side-column">
        <InsightPanel
          :insight="state.insightData"
          :loading="state.loadingInsight"
        />

        <KeywordCloud
          :keywords="keywords"
          :loading="state.loadingDashboard"
        />
      </div>
    </div>
  </div>
</template>
