<!-- frontend/src/components/ArticleList.vue -->

<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
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
const showAll = ref(false);

const displayedArticles = computed(() => {
  return showAll.value ? props.articles : props.articles.slice(0, 3);
});

watch(
  () => props.articles,
  () => {
    showAll.value = false;
  }
);


// 依 push_count 決定 badge 的 class。
function getPushClass(pushCount) {
  if (pushCount >= 50) return "push-hot";
  if (pushCount >= 10) return "push-warm";
  if (pushCount < 0) return "push-negative";
  return "push-normal";
}

function formatDate(dateText) {
  if (!dateText) return "no date";

  return String(dateText).slice(0, 10);
}

function getSource(article) {
  const board = article.board || "unknown";
  const author = article.author || "unknown";

  return `${board} / ${author}`;
}
</script>

<template>
  <section class="card article-card">
    <div class="section-header article-header">
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

    <div v-else class="article-table-wrap">
      <table class="article-table">
        <thead>
          <tr>
            <th>排名</th>
            <th>標題</th>
            <th>來源</th>
            <th>回文數</th>
            <th>日期</th>
            <th>摘要</th>
          </tr>
        </thead>

        <tbody>
          <tr
            v-for="(article, index) in displayedArticles"
            :key="article.id"
          >
            <td class="article-rank-cell">
              <span class="rank-badge">{{ index + 1 }}</span>
            </td>

            <td class="article-title-cell">
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
            </td>

            <td class="article-source-cell">
              {{ getSource(article) }}
            </td>

            <td>
              <span class="push-badge" :class="getPushClass(article.push_count)">
                {{ article.push_count }}
              </span>
            </td>

            <td class="article-date-cell">
              {{ formatDate(article.published_at) }}
            </td>

            <td class="article-preview-cell">
              {{ article.preview }}
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="articles.length > 3" class="article-more-row">
        <button
          class="secondary-button article-more-button"
          type="button"
          @click="showAll = !showAll"
        >
          {{ showAll ? "收合文章" : `查看更多（還有 ${articles.length - 3} 篇）` }}
        </button>
      </div>
    </div>
  </section>
</template>
