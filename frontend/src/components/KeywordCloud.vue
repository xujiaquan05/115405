<!-- frontend/src/components/KeywordCloud.vue -->

<script setup>
import { computed } from "vue";

const props = defineProps({
  keywords: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const cloudColors = [
  "#2f343f",
  "#5aa7f2",
  "#64cdb4",
  "#f08b76",
  "#8c86e8",
  "#f3c74f",
  "#ef5675",
  "#25a0a5",
  "#77d968",
  "#ff9f43",
];

const cloudPositions = [
  { left: 50, top: 50, rotate: 0 },
  { left: 35, top: 50, rotate: 0 },
  { left: 64, top: 46, rotate: 0 },
  { left: 44, top: 64, rotate: 0 },
  { left: 56, top: 34, rotate: 0 },
  { left: 28, top: 36, rotate: 0 },
  { left: 72, top: 59, rotate: 0 },
  { left: 38, top: 27, rotate: 0 },
  { left: 61, top: 72, rotate: 0 },
  { left: 25, top: 63, rotate: 0 },
  { left: 76, top: 32, rotate: 0 },
  { left: 48, top: 22, rotate: 0 },
  { left: 68, top: 22, rotate: 0 },
  { left: 32, top: 76, rotate: 0 },
  { left: 56, top: 56, rotate: 0 },
  { left: 43, top: 80, rotate: 0 },
  { left: 76, top: 75, rotate: 0 },
  { left: 22, top: 25, rotate: 0 },
  { left: 66, top: 82, rotate: 0 },
  { left: 52, top: 84, rotate: 0 },
];

const cloudItems = computed(() => {
  const counts = props.keywords.map((item) => item.count || 0);
  const maxCount = Math.max(...counts, 1);
  const minCount = Math.min(...counts, maxCount);
  const range = Math.max(maxCount - minCount, 1);

  return props.keywords.slice(0, 20).map((item, index) => {
    const weight = ((item.count || 0) - minCount) / range;
    const fontSize = Math.round(18 + weight * 34 + Math.max(0, 6 - index) * 2);
    const position = cloudPositions[index % cloudPositions.length];

    return {
      keyword: item.keyword,
      count: item.count,
      style: {
        left: `${position.left}%`,
        top: `${position.top}%`,
        color: cloudColors[index % cloudColors.length],
        fontSize: `${fontSize}px`,
        "--cloud-size": `${fontSize}px`,
        transform: `translate(-50%, -50%) rotate(${position.rotate}deg)`,
        zIndex: 30 - index,
      },
    };
  });
});
</script>

<template>
  <section class="card keyword-cloud-card">
    <h2 class="section-title">高頻關鍵詞</h2>

    <div v-if="loading" class="keyword-cloud-canvas">
      <span class="skeleton keyword-skeleton cloud-skeleton-1"></span>
      <span class="skeleton keyword-skeleton cloud-skeleton-2"></span>
      <span class="skeleton keyword-skeleton cloud-skeleton-3"></span>
    </div>

    <div v-else-if="keywords.length === 0" class="empty-state">
      目前沒有高頻詞資料。
    </div>

    <div v-else class="keyword-cloud-canvas" aria-label="高頻關鍵詞文字雲">
      <span
        v-for="item in cloudItems"
        :key="item.keyword"
        class="keyword-cloud-word"
        :style="item.style"
        :title="`${item.keyword}：${item.count}`"
      >
        {{ item.keyword }}
      </span>
    </div>
  </section>
</template>
