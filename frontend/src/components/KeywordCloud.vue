<!-- frontend/src/components/KeywordCloud.vue -->

<script setup>
defineProps({
  keywords: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
});


// Note:
// count càng lớn thì class càng lớn.
// Dùng để làm keyword cloud nhìn trực quan hơn.
function getKeywordSize(count) {
  if (count >= 10) return "keyword-large";
  if (count >= 5) return "keyword-medium";
  return "keyword-small";
}
</script>

<template>
  <section class="card">
    <h2 class="section-title">高頻關鍵詞</h2>

    <div v-if="loading" class="keyword-cloud">
      <span class="skeleton keyword-skeleton"></span>
      <span class="skeleton keyword-skeleton"></span>
      <span class="skeleton keyword-skeleton"></span>
    </div>

    <div v-else-if="keywords.length === 0" class="empty-state">
      目前沒有高頻詞資料。
    </div>

    <div v-else class="keyword-cloud">
      <span
        v-for="item in keywords"
        :key="item.keyword"
        class="keyword-pill"
        :class="getKeywordSize(item.count)"
      >
        {{ item.keyword }}
        <strong>{{ item.count }}</strong>
      </span>
    </div>
  </section>
</template>