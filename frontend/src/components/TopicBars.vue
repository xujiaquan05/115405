<!-- frontend/src/components/TopicBars.vue -->

<script setup>
import { computed } from "vue";

const props = defineProps({
  topics: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const visibleTopics = computed(() => props.topics.slice(0, 6));

const maxCount = computed(() => {
  return Math.max(...visibleTopics.value.map((topic) => Number(topic.count || 0)), 1);
});

const topicColors = [
  "#0f9f6e",
  "#0891b2",
  "#6366f1",
  "#f59e0b",
  "#ef4444",
  "#64748b",
];
</script>

<template>
  <section class="card compact-analysis-card">
    <h2 class="section-title">熱門話題</h2>

    <div v-if="loading">
      <div class="skeleton compact-row-skeleton"></div>
      <div class="skeleton compact-row-skeleton"></div>
      <div class="skeleton compact-row-skeleton"></div>
    </div>

    <div v-else-if="topics.length === 0" class="empty-state">
      目前沒有話題資料。
    </div>

    <div v-else class="topic-chart-list">
      <div
        v-for="(topic, index) in visibleTopics"
        :key="topic.keyword"
        class="topic-chart-row"
      >
        <div class="topic-chart-meta">
          <span>{{ index + 1 }}</span>
          <strong>{{ topic.keyword }}</strong>
          <em>{{ topic.count }} 則</em>
        </div>

        <div class="topic-chart-track">
          <div
            class="topic-chart-fill"
            :style="{
              width: `${Math.max(8, (Number(topic.count || 0) / maxCount) * 100)}%`,
              backgroundColor: topicColors[index % topicColors.length],
            }"
          ></div>
        </div>
      </div>
    </div>
  </section>
</template>
