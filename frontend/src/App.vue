<!-- frontend/src/App.vue -->

<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import AppNavbar from "./components/AppNavbar.vue";

const route = useRoute();

// 登入頁與公開首頁（landing）都是全螢幕版面，不顯示系統 Navbar。
const isLoginPage = computed(() => route.path === "/login");
const isLandingPage = computed(() => route.path === "/");
const hideNavbar = computed(() => isLoginPage.value || isLandingPage.value);

const mainClass = computed(() => {
  if (isLoginPage.value) return "login-content";
  if (isLandingPage.value) return "landing-content";
  return "main-content";
});
</script>

<template>
  <div class="app-shell">
    <!-- 全站共用的 Navbar，
      裡面有 Dashboard / QA / History 的切換連結。
      登入頁與公開首頁不顯示。
    -->
    <AppNavbar v-if="!hideNavbar" />

    <!-- RouterView 是 Vue Router 依目前 URL 渲染頁面的位置，
      例如 "/dashboard" 會渲染 DashboardView.vue。
    -->
    <main :class="mainClass">
      <RouterView />
    </main>
  </div>
</template>
