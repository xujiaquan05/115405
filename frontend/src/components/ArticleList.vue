<!-- frontend/src/components/ArticleList.vue -->

<script setup>
defineProps({
  articles: {
    type: Array,
    default: () => [],
  },
  sortBy: {
    type: String,
    default: "push_count",
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(["change-sort"]);


// Note:
// Dựa vào push_count để quyết định badge class.
function getPushClass(pushCount) {
  if (pushCount >= 50) return "push-hot";
  if (pushCount >= 10) return "push-warm";
  if (pushCount < 0) return "push-negative";
  return "push-normal";
}
</script>

<template>
  <section class="card">
    <div class="section-header">
      <div>
        <h2 class="section-title">熱門文章</h2>
        <p class="section-desc">點擊標題可開啟 PTT 原文。</p>
      </div>

      <div class="sort-buttons">
        <button
          :class="{ active: sortBy === 'push_count' }"
          @click="emit('change-sort', 'push_count')"
        >
          推文數
        </button>

        <button
          :class="{ active: sortBy === 'latest' }"
          @click="emit('change-sort', 'latest')"
        >
          最新
        </button>

        <button
          :class="{ active: sortBy === 'relevance' }"
          @click="emit('change-sort', 'relevance')"
        >
          相關度
        </button>
      </div>
    </div>

    <div v-if="loading">
      <div class="skeleton article-skeleton"></div>
      <div class="skeleton article-skeleton"></div>
      <div class="skeleton article-skeleton"></div>
    </div>

    <div v-else-if="articles.length === 0" class="empty-state">
      目前沒有相關文章。
    </div>

    <div v-else class="article-list">
      <article
        v-for="article in articles"
        :key="article.id"
        class="article-item"
      >
        <div class="article-main">
          <!-- Note:
            target="_blank" 讓 PTT 原文在新分頁開啟。
          -->
          <a
            class="article-title"
            :href="article.url"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{ article.title }}
          </a>

          <p class="article-meta">
            {{ article.board }} · {{ article.author || "unknown" }} ·
            {{ article.published_at || "no date" }}
          </p>

          <p class="article-preview">
            {{ article.preview }}
          </p>
        </div>

        <span class="push-badge" :class="getPushClass(article.push_count)">
          {{ article.push_count }}
        </span>
      </article>
    </div>
  </section>
</template>