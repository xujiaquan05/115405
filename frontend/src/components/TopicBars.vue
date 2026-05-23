<!-- frontend/src/components/TopicBars.vue -->

<script setup>
defineProps({
  topics: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <section class="card compact-analysis-card">
    <h2 class="section-title">熱門子話題</h2>

    <div v-if="loading">
      <div class="skeleton compact-row-skeleton"></div>
      <div class="skeleton compact-row-skeleton"></div>
      <div class="skeleton compact-row-skeleton"></div>
    </div>

    <div v-else-if="topics.length === 0" class="empty-state">
      目前沒有話題資料。
    </div>

    <ol v-else class="topic-ranking-list">
      <li
        v-for="(topic, index) in topics.slice(0, 6)"
        :key="topic.keyword"
      >
        <span>{{ index + 1 }}</span>
        <strong>{{ topic.keyword }}</strong>
        <em>{{ topic.count }} 則</em>
      </li>
    </ol>
  </section>
</template>
