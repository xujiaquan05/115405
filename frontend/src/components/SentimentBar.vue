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
</script>

<template>
  <section class="card">
    <h2 class="section-title">情緒分布</h2>

    <div v-if="loading" class="skeleton skeleton-bar"></div>

    <div v-else>
      <!-- Note:
        用三段 div 組成一條 sentiment bar。
        width 根據 positive / neutral / negative 百分比改變。
      -->
      <div class="sentiment-bar">
        <div
          class="sentiment-positive"
          :style="{ width: `${sentiment.positive || 0}%` }"
        ></div>

        <div
          class="sentiment-neutral"
          :style="{ width: `${sentiment.neutral || 0}%` }"
        ></div>

        <div
          class="sentiment-negative"
          :style="{ width: `${sentiment.negative || 0}%` }"
        ></div>
      </div>

      <div class="sentiment-labels">
        <span>正面 {{ sentiment.positive || 0 }}%</span>
        <span>中性 {{ sentiment.neutral || 0 }}%</span>
        <span>負面 {{ sentiment.negative || 0 }}%</span>
      </div>
    </div>
  </section>
</template>