<!-- frontend/src/App.vue -->

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import AppNavbar from "./components/AppNavbar.vue";

const route = useRoute();

// 登入頁是全螢幕版面，不顯示 Navbar。
const isLoginPage = computed(() => route.path === "/login");
</script>

<template>
  <div class="app-shell">
    <!-- 全站共用的 Navbar，
      裡面有 Dashboard / QA / History 的切換連結。
    -->
    <AppNavbar v-if="!isLoginPage" />

    <!-- RouterView 是 Vue Router 依目前 URL 渲染頁面的位置，
      例如 "/" 會渲染 DashboardView.vue。
    -->
    <main :class="isLoginPage ? 'login-content' : 'main-content'">
      <RouterView />
    </main>
  </div>
</template>
