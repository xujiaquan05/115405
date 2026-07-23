<!-- frontend/src/components/LogoMark.vue -->
<!-- MeBOD 專案 logo 圖示：漸層方塊 + 上升長條圖 + 亮點。 -->

<script setup>
defineProps({
  size: {
    type: Number,
    default: 40,
  },
});

// 每個實例用獨立的漸層 id，避免同一頁多個 logo 時 id 衝突。
const uid = Math.random().toString(36).slice(2, 8);
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 40 40"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    class="logo-mark"
    aria-hidden="true"
  >
    <defs>
      <linearGradient :id="`lg-${uid}`" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
        <stop stop-color="#4f46e5" />
        <stop offset="1" stop-color="#7c3aed" />
      </linearGradient>
    </defs>
    <rect width="40" height="40" rx="11" :fill="`url(#lg-${uid})`" />
    <rect x="9.5" y="21" width="5" height="9" rx="2" fill="#ffffff" opacity="0.82" />
    <rect x="17.5" y="16" width="5" height="14" rx="2" fill="#ffffff" opacity="0.92" />
    <rect x="25.5" y="11" width="5" height="19" rx="2" fill="#ffffff" />
    <path
      d="M12 8.2 l0.9 1.9 1.9 0.9 -1.9 0.9 -0.9 1.9 -0.9 -1.9 -1.9 -0.9 1.9 -0.9 z"
      fill="#ffffff"
      opacity="0.95"
    />
  </svg>
</template>
