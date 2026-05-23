<!-- frontend/src/components/SentimentBar.vue -->

<script setup>
defineProps({
  sentiment: {
    type: Object,
    default: () => ({}),
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const sentimentRows = [
  { key: "positive", label: "正面", color: "#64cdb4" },
  { key: "neutral", label: "中性", color: "#dfddd3" },
  { key: "negative", label: "負面", color: "#f08b76" },
];
</script>

<template>
  <section class="card compact-analysis-card">
    <h2 class="section-title">情緒分布</h2>

    <div v-if="loading">
      <div class="skeleton compact-row-skeleton"></div>
      <div class="skeleton compact-row-skeleton"></div>
      <div class="skeleton compact-row-skeleton"></div>
    </div>

    <div v-else class="sentiment-rank-list">
      <div
        v-for="row in sentimentRows"
        :key="row.key"
        class="sentiment-rank-row"
      >
        <span class="sentiment-rank-label">{{ row.label }}</span>
        <div class="sentiment-rank-track">
          <div
            class="sentiment-rank-fill"
            :style="{
              width: `${sentiment[row.key] || 0}%`,
              backgroundColor: row.color,
            }"
          ></div>
        </div>
        <strong>{{ sentiment[row.key] || 0 }}%</strong>
      </div>
    </div>
  </section>
</template>
