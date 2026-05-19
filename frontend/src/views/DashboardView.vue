<!-- frontend/src/views/DashboardView.vue -->

<script setup>
import { onMounted } from "vue";

import SearchBar from "../components/SearchBar.vue";
import MetricsRow from "../components/MetricsRow.vue";
import SentimentBar from "../components/SentimentBar.vue";
import TrendChart from "../components/TrendChart.vue";
import ArticleList from "../components/ArticleList.vue";
import InsightPanel from "../components/InsightPanel.vue";
import KeywordCloud from "../components/KeywordCloud.vue";

import { useDashboard } from "../composables/useDashboard.js";

const {
  state,
  overview,
  sentiment,
  trend,
  hotArticles,
  keywords,
  searchDashboard,
  changeSort,
} = useDashboard();


// Note:
// Khi mở Dashboard lần đầu, tự động load keyword mặc định.
onMounted(() => {
  searchDashboard();
});
</script>

<template>
  <div class="dashboard-page">
    <SearchBar />

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