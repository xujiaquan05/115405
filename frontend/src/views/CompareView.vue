<!-- frontend/src/views/CompareView.vue -->

<script setup>
import { computed, reactive, ref } from "vue";
import api from "../services/api.js";

const state = reactive({
  input: "玻尿酸, 肉毒",
  days: 30,
  loading: false,
  errorMessage: "",
  results: [],
});

const dayOptions = [7, 30, 90];

const maxArticles = computed(() => {
  return Math.max(1, ...state.results.map((r) => r.article_count || 0));
});

function scoreClass(score) {
  if (score >= 60) return "good";
  if (score >= 45) return "neutral";
  return "bad";
}

async function runCompare() {
  const keywords = state.input
    .split(/[,，\s]+/)
    .map((k) => k.trim())
    .filter(Boolean)
    .slice(0, 5);

  if (!keywords.length) {
    state.errorMessage = "請至少輸入一個關鍵字。";
    return;
  }

  state.loading = true;
  state.errorMessage = "";

  try {
    const response = await api.get("/api/analysis/compare", {
      params: { keywords, days: state.days },
    });
    state.results = response.data.data.results;
    if (!state.results.length) {
      state.errorMessage = "找不到資料，請換關鍵字或先執行爬蟲。";
    }
  } catch (error) {
    console.error(error);
    state.errorMessage = "比較失敗，請確認 backend 是否正在執行。";
  } finally {
    state.loading = false;
  }
}

function formatGrowth(value) {
  const n = Number(value || 0);
  return `${n > 0 ? "+" : ""}${n}%`;
}

runCompare();
</script>

<template>
  <section class="compare-page">
    <div class="compare-header">
      <h2>競品比較</h2>
      <p>輸入多個關鍵字（品牌或療程），並排比較聲量、情緒與成長，快速看出「我 vs 競品」。</p>
    </div>

    <form class="compare-toolbar" @submit.prevent="runCompare">
      <input
        v-model="state.input"
        type="text"
        placeholder="輸入關鍵字，用逗號分隔，例如：玻尿酸, 肉毒, 皮秒雷射"
      />
      <select v-model.number="state.days">
        <option v-for="d in dayOptions" :key="d" :value="d">近 {{ d }} 天</option>
      </select>
      <button type="submit" :disabled="state.loading">
        {{ state.loading ? "比較中…" : "開始比較" }}
      </button>
    </form>

    <p v-if="state.errorMessage" class="error-message">{{ state.errorMessage }}</p>

    <div v-if="state.results.length" class="compare-grid">
      <article
        v-for="result in state.results"
        :key="result.keyword"
        class="compare-card"
      >
        <h3>{{ result.keyword }}</h3>

        <div class="compare-score">
          <span :class="['compare-score-pill', scoreClass(result.sentiment_score)]">
            {{ result.sentiment_score }}
          </span>
          <span class="compare-score-label">情緒分數</span>
        </div>

        <div class="compare-metric">
          <span>文章數</span>
          <strong>{{ result.article_count }}</strong>
        </div>
        <div class="compare-bar-track">
          <div
            class="compare-bar"
            :style="{ width: `${Math.round((result.article_count / maxArticles) * 100)}%` }"
          ></div>
        </div>

        <!-- 情緒分布 -->
        <div class="compare-senti-bar">
          <div class="seg pos" :style="{ width: `${result.positive}%` }" :title="`正面 ${result.positive}%`"></div>
          <div class="seg neu" :style="{ width: `${result.neutral}%` }" :title="`中性 ${result.neutral}%`"></div>
          <div class="seg neg" :style="{ width: `${result.negative}%` }" :title="`負面 ${result.negative}%`"></div>
        </div>
        <div class="compare-senti-legend">
          <span>正 {{ result.positive }}%</span>
          <span>中 {{ result.neutral }}%</span>
          <span>負 {{ result.negative }}%</span>
        </div>

        <div class="compare-metric-row">
          <div>
            <span>成長率</span>
            <strong :class="Number(result.growth_rate) >= 0 ? 'up' : 'down'">
              {{ formatGrowth(result.growth_rate) }}
            </strong>
          </div>
          <div>
            <span>平均推文</span>
            <strong>{{ result.avg_push_count }}</strong>
          </div>
        </div>

        <p class="compare-coverage">AI 評分覆蓋率 {{ result.ai_rated_percent }}%</p>
      </article>
    </div>
  </section>
</template>
