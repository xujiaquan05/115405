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

function getWidth(count, topics) {
  const maxCount = Math.max(...topics.map((topic) => topic.count || 0), 1);
  return `${Math.max((count / maxCount) * 100, 8)}%`;
}
</script>

<template>
  <section class="card topic-card">
    <h2 class="section-title">熱門子話題</h2>

    <div v-if="loading">
      <div class="skeleton topic-skeleton"></div>
      <div class="skeleton topic-skeleton"></div>
      <div class="skeleton topic-skeleton"></div>
    </div>

    <div v-else-if="topics.length === 0" class="empty-state">
      目前沒有話題資料。
    </div>

    <div v-else class="topic-list">
      <div
        v-for="topic in topics.slice(0, 5)"
        :key="topic.keyword"
        class="topic-row"
      >
        <span class="topic-name">{{ topic.keyword }}</span>
        <div class="topic-track">
          <div
            class="topic-fill"
            :style="{ width: getWidth(topic.count, topics) }"
          ></div>
        </div>
        <span class="topic-count">{{ topic.count }}</span>
      </div>
    </div>
  </section>
</template>
