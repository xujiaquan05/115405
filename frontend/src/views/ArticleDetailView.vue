<!-- frontend/src/views/ArticleDetailView.vue -->

<script setup>
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
      >在 PTT 開啟原文 ↗</a>
    </article>
  </section>
</template>
