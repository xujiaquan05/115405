<!-- frontend/src/views/ArticleDetailView.vue -->

<script setup>
// 留言統計與逐則情緒（由後端 /api/articles/{id} 一併回傳）。
import { computed, onMounted, reactive, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "../services/api.js";

const route = useRoute();
const router = useRouter();

const state = reactive({
  loading: true,
  errorMessage: "",
  article: null,
});

const comments = computed(() => state.article?.comments || { total: 0, rated: 0, items: [] });

// 依來源平台顯示正確的連結文字，不再一律寫「在 PTT 開啟」。
const PLATFORM_LABELS = { ptt: "PTT", dcard: "Dcard", mobile01: "Mobile01", threads: "Threads" };
const sourceLinkLabel = computed(() => {
  const platform = state.article?.platform;
  return `在 ${PLATFORM_LABELS[platform] || "原網站"} 開啟原文`;
});

function commentLabel(sentiment) {
  return { positive: "正面", neutral: "中性", negative: "負面" }[sentiment] || "未評分";
}

function commentClass(sentiment) {
  return { positive: "is-positive", neutral: "is-neutral", negative: "is-negative" }[sentiment] || "is-none";
}

const sentimentInfo = computed(() => {
  const map = {
    positive: { label: "正面", cls: "is-positive" },
    neutral: { label: "中性", cls: "is-neutral" },
    negative: { label: "負面", cls: "is-negative" },
  };
  return map[state.article?.sentiment] || null;
});

async function fetchArticle() {
  state.loading = true;
  state.errorMessage = "";

  try {
    const response = await api.get(`/api/articles/${route.params.id}`);
    state.article = response.data.data;
  } catch (error) {
    console.error(error);
    state.errorMessage = error.response?.status === 404
      ? "找不到這篇文章。"
      : "文章載入失敗，請稍後再試。";
  } finally {
    state.loading = false;
  }
}

onMounted(fetchArticle);
watch(() => route.params.id, fetchArticle);
</script>

<template>
  <section class="article-detail-page">
    <button type="button" class="article-detail-back" @click="router.back()">← 返回</button>

    <p v-if="state.errorMessage" class="error-message">{{ state.errorMessage }}</p>
    <p v-else-if="state.loading" class="article-detail-loading">文章載入中…</p>

    <article v-else-if="state.article" class="card article-detail-card">
      <h2 class="article-detail-title">{{ state.article.title }}</h2>

      <div class="article-detail-meta">
        <span>{{ state.article.board }}</span>
        <span>{{ state.article.author }}</span>
        <span>推 {{ state.article.push_count }}</span>
        <span>{{ state.article.published_at }}</span>
        <span
          v-if="sentimentInfo"
          :class="['article-detail-sentiment', sentimentInfo.cls]"
        >{{ sentimentInfo.label }}</span>
        <span v-else class="article-detail-sentiment is-none">未評分</span>
      </div>

      <div class="article-detail-content">{{ state.article.content || "（此文章沒有內文）" }}</div>

      <a
        class="article-detail-link"
        :href="state.article.url"
        target="_blank"
        rel="noopener noreferrer"
      >{{ sourceLinkLabel }} ↗</a>

      <!-- 留言區：獨立儲存後才能逐則顯示情緒與統計 -->
      <section v-if="comments.total" class="article-comments">
        <div class="article-comments-head">
          <h3>留言情緒（{{ comments.total }} 則）</h3>
          <div class="article-comments-stats">
            <span class="is-positive">正面 {{ comments.positive }}%</span>
            <span class="is-neutral">中性 {{ comments.neutral }}%</span>
            <span class="is-negative">負面 {{ comments.negative }}%</span>
          </div>
        </div>

        <p v-if="comments.rated < comments.total" class="article-comments-hint">
          已評分 {{ comments.rated }} / {{ comments.total }} 則，比例以已評分的留言計算。
        </p>

        <ul class="article-comments-list">
          <li v-for="item in comments.items" :key="item.floor">
            <span :class="['article-comment-tag', commentClass(item.sentiment)]">
              {{ commentLabel(item.sentiment) }}
            </span>
            <p>{{ item.content }}</p>
          </li>
        </ul>
      </section>
    </article>
  </section>
</template>
