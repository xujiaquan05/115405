<!-- frontend/src/App.vue -->

<script setup>
import AppNavbar from "./components/AppNavbar.vue";
</script>

<template>
  <div class="app-shell">
    <!-- 全站共用的 Navbar，
      裡面有 Dashboard / QA / History 的切換連結。
    -->
    <AppNavbar />

    <!-- RouterView 是 Vue Router 依目前 URL 渲染頁面的位置，
      例如 "/" 會渲染 DashboardView.vue。
    -->
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>