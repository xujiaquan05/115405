<!-- frontend/src/components/DataStatusCard.vue -->

<script setup>
defineProps({
  status: {
    type: Object,
    default: () => ({}),
  },
  loading: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <section class="data-status-card">
    <div>
      <p class="data-status-label">資料狀態</p>
      <p v-if="loading" class="data-status-main">資料更新中...</p>
      <p v-else class="data-status-main">
        最後更新：{{ status.latest_published_at || "尚無資料" }}
      </p>
      <p class="data-status-meta">
        來源：{{ status.source || "PTT" }} ·
        狀態：{{ status.status === "normal" ? "正常" : "尚未建立資料" }}
      </p>
    </div>

    <RouterLink to="/crawl" class="secondary-button data-status-button">
      前往爬蟲管理
    </RouterLink>
  </section>
</template>
