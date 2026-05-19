<!-- frontend/src/components/MetricsRow.vue -->

<script setup>
defineProps({
  overview: {
    type: Object,
    default: () => ({}),
  },
  sentiment: {
    type: Object,
    default: () => ({}),
  },
  loading: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <section class="metrics-grid">
    <div class="metric-card">
      <p class="metric-label">相關文章數</p>

      <!-- Note:
        loading 時顯示 skeleton，避免頁面空白。
      -->
      <div v-if="loading" class="skeleton skeleton-number"></div>
      <h3 v-else class="metric-value">{{ overview.total_articles || 0 }}</h3>

      <p class="metric-change">
        成長率：{{ overview.growth_rate || 0 }}%
      </p>
    </div>

    <div class="metric-card">
      <p class="metric-label">平均推文數</p>
      <div v-if="loading" class="skeleton skeleton-number"></div>
      <h3 v-else class="metric-value">{{ overview.avg_push_count || 0 }}</h3>
      <p class="metric-change">反映討論熱度</p>
    </div>

    <div class="metric-card">
      <p class="metric-label">正面比例</p>
      <div v-if="loading" class="skeleton skeleton-number"></div>
      <h3 v-else class="metric-value">{{ sentiment.positive || 0 }}%</h3>
      <p class="metric-change">依推文數粗略估計</p>
    </div>

    <div class="metric-card">
      <p class="metric-label">負面預警數</p>
      <div v-if="loading" class="skeleton skeleton-number"></div>
      <h3 v-else class="metric-value">{{ overview.negative_count || 0 }}</h3>
      <p class="metric-change danger">需留意負面文章</p>
    </div>
  </section>
</template>