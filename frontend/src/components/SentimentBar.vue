<!-- frontend/src/components/SentimentBar.vue -->

<script setup>
import { computed } from "vue";

const props = defineProps({
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

const pieStyle = computed(() => {
  const positive = Number(props.sentiment.positive || 0);
  const neutral = Number(props.sentiment.neutral || 0);
  const negative = Number(props.sentiment.negative || 0);
  const total = positive + neutral + negative;

  if (!total) {
    return {
      background: "conic-gradient(#e5e7eb 0deg 360deg)",
    };
  }

  const positiveDeg = (positive / total) * 360;
  const neutralDeg = positiveDeg + (neutral / total) * 360;

  return {
    background: `conic-gradient(
      #64cdb4 0deg ${positiveDeg}deg,
      #dfddd3 ${positiveDeg}deg ${neutralDeg}deg,
      #f08b76 ${neutralDeg}deg 360deg
    )`,
  };
});
</script>

<template>
  <section class="card compact-analysis-card">
    <h2 class="section-title">情緒分佈</h2>

    <div v-if="loading">
      <div class="skeleton compact-row-skeleton"></div>
      <div class="skeleton compact-row-skeleton"></div>
      <div class="skeleton compact-row-skeleton"></div>
    </div>

    <div v-else class="sentiment-pie-layout">
      <div class="sentiment-pie" :style="pieStyle"></div>

      <div class="sentiment-pie-legend">
        <div
          v-for="row in sentimentRows"
          :key="row.key"
          class="sentiment-pie-legend-row"
        >
          <span :style="{ backgroundColor: row.color }"></span>
          <strong>{{ row.label }}</strong>
          <em>{{ sentiment[row.key] || 0 }}%</em>
        </div>
      </div>
    </div>
  </section>
</template>
