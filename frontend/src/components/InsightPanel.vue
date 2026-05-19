<!-- frontend/src/components/InsightPanel.vue -->

<script setup>
defineProps({
  insight: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <section class="card insight-card">
    <h2 class="section-title">LLM 洞察分析</h2>

    <div v-if="loading">
      <div class="skeleton insight-skeleton"></div>
      <div class="skeleton insight-skeleton small"></div>
    </div>

    <div v-else-if="!insight" class="empty-state">
      尚未取得 LLM 分析資料。
    </div>

    <div v-else>
      <p class="insight-summary">
        {{ insight.summary || insight.trend_summary || "目前沒有摘要。" }}
      </p>

      <div class="insight-block">
        <h3>熱門話題</h3>
        <ul>
          <li v-for="topic in insight.hot_topics || []" :key="topic">
            ↑ {{ topic }}
          </li>
        </ul>
      </div>

      <div class="insight-block">
        <h3>消費者痛點</h3>
        <ul>
          <li v-for="pain in insight.consumer_pain_points || []" :key="pain">
            ! {{ pain }}
          </li>
        </ul>
      </div>

      <div class="insight-block">
        <h3>行銷建議</h3>
        <ul>
          <li
            v-for="suggestion in insight.marketing_suggestions || []"
            :key="suggestion"
          >
            i {{ suggestion }}
          </li>
        </ul>
      </div>

      <!-- Note:
        深度分析按鈕先放 UI。
        後面可以接 Phase 4 force_refresh=true 或 Phase 7 QA。
      -->
      <button class="secondary-button">
        深度分析
      </button>
    </div>
  </section>
</template>