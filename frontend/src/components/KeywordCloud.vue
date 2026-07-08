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

const cloudArea = {
  width: 1000,
  height: 330,
  padding: 18,
};

const estimateWordWidth = (keyword, fontSize) => {
  return [...String(keyword)].reduce((width, char) => {
    return width + fontSize * (/[\u4e00-\u9fff]/.test(char) ? 1 : 0.58);
  }, 18);
};

const overlaps = (box, boxes) => {
  const spacing = 14;
  return boxes.some((placed) => {
    return !(
      box.right + spacing < placed.left ||
      box.left - spacing > placed.right ||
      box.bottom + spacing < placed.top ||
      box.top - spacing > placed.bottom
    );
  });
};

const candidatePositions = Array.from({ length: 90 }, (_, index) => {
  if (index === 0) {
    return { x: 500, y: 165 };
  }

  const angle = index * 2.35;
  const radius = 22 + index * 5.2;

  return {
    x: 500 + Math.cos(angle) * radius * 1.55,
    y: 165 + Math.sin(angle) * radius * 0.78,
  };
});

const createWordPlacement = (keyword, preferredFontSize, placedBoxes) => {
  for (let shrink = 0; shrink <= 12; shrink += 2) {
    const fontSize = Math.max(16, preferredFontSize - shrink);
    const width = estimateWordWidth(keyword, fontSize);
    const height = fontSize * 1.08;

    for (const position of candidatePositions) {
      const box = {
        left: position.x - width / 2,
        right: position.x + width / 2,
        top: position.y - height / 2,
        bottom: position.y + height / 2,
      };

      const inside =
        box.left >= cloudArea.padding &&
        box.right <= cloudArea.width - cloudArea.padding &&
        box.top >= cloudArea.padding &&
        box.bottom <= cloudArea.height - cloudArea.padding;

      if (inside && !overlaps(box, placedBoxes)) {
        placedBoxes.push(box);
        return {
          fontSize,
          left: (position.x / cloudArea.width) * 100,
          top: (position.y / cloudArea.height) * 100,
        };
      }
    }
  }

  const fallbackIndex = placedBoxes.length;
  return {
    fontSize: Math.max(16, preferredFontSize - 12),
    left: 18 + (fallbackIndex % 5) * 16,
    top: 18 + Math.floor(fallbackIndex / 5) * 16,
  };
};

const cloudItems = computed(() => {
  const counts = props.keywords.map((item) => item.count || 0);
  const maxCount = Math.max(...counts, 1);
  const minCount = Math.min(...counts, maxCount);
  const range = Math.max(maxCount - minCount, 1);
  const placedBoxes = [];

  return props.keywords.slice(0, 20).map((item, index) => {
    const weight = ((item.count || 0) - minCount) / range;
    const preferredFontSize = Math.round(18 + weight * 34 + Math.max(0, 6 - index) * 2);
    const placement = createWordPlacement(item.keyword, preferredFontSize, placedBoxes);

    return {
      keyword: item.keyword,
      count: item.count,
      style: {
        left: `${placement.left}%`,
        top: `${placement.top}%`,
        color: cloudColors[index % cloudColors.length],
        fontSize: `${placement.fontSize}px`,
        "--cloud-size": `${placement.fontSize}px`,
        transform: "translate(-50%, -50%)",
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
