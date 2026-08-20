<!-- frontend/src/components/PlatformComparison.vue -->

<script setup>
import { computed } from "vue";

const props = defineProps({
  rows: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const PLATFORM_LABELS = { ptt: "PTT", dcard: "Dcard", mobile01: "Mobile01", threads: "Threads" };

function platformLabel(name) {
  return PLATFORM_LABELS[name] || name;
}

// 聲量長條以「最高聲量的平台」為 100%。
const maxArticles = computed(() => {
  return Math.max(1, ...props.rows.map((row) => row.total_articles || 0));
});

function volumeWidth(row) {
  return `${Math.round(((row.total_articles || 0) / maxArticles.value) * 100)}%`;
}

// 淨情緒分數：50 為中性，越高越正面。
function scoreClass(score) {
  if (score >= 60) return "good";
  if (score <= 45) return "bad";
  return "neutral";
}
</script>

<template>
  <section class="card platform-compare-card">
    <h2 class="section-title">平台比較</h2>
    <p class="platform-compare-hint">
      同一個關鍵字在各平台的聲量、互動與情緒差異，可用來判斷該在哪個平台溝通、用什麼語氣。
    </p>

    <div v-if="loading">
      <div class="skeleton compact-row-skeleton"></div>
      <div class="skeleton compact-row-skeleton"></div>
    </div>

    <p v-else-if="!rows.length" class="platform-compare-empty">
      這個關鍵字在目前條件下沒有資料。
    </p>

    <div v-else class="platform-compare-list">
      <article v-for="row in rows" :key="row.platform" class="platform-compare-row">
        <header>
          <strong>{{ platformLabel(row.platform) }}</strong>
          <span :class="['platform-compare-score', scoreClass(row.sentiment_score)]">
            情緒 {{ row.sentiment_score }}
          </span>
        </header>

        <div class="platform-compare-bar">
          <div class="platform-compare-bar-fill" :style="{ width: volumeWidth(row) }"></div>
        </div>

        <dl class="platform-compare-stats">
          <div>
            <dt>聲量</dt>
            <dd>{{ row.total_articles }} 篇</dd>
          </div>
          <div>
            <dt>平均互動</dt>
            <dd>{{ row.avg_push_count }}</dd>
          </div>
          <div>
            <dt>正面</dt>
            <dd class="is-positive">{{ row.positive }}%</dd>
          </div>
          <div>
            <dt>負面</dt>
            <dd class="is-negative">{{ row.negative }}%</dd>
          </div>
          <div>
            <dt>AI 覆蓋</dt>
            <dd>{{ row.ai_rated_percent }}%</dd>
          </div>
        </dl>
      </article>
    </div>
  </section>
</template>
