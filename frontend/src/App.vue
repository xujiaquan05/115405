<!-- frontend/src/App.vue -->

<script setup>
import AppNavbar from "./components/AppNavbar.vue";
</script>

<template>
  <div class="app-shell">
    <!-- Note:
      Navbar dùng chung cho toàn bộ hệ thống.
      Bên trong có link chuyển giữa Dashboard / QA / History.
    -->
    <AppNavbar />

    <!-- Note:
      RouterView là nơi Vue Router render page tương ứng với URL hiện tại.
      Ví dụ "/" sẽ render DashboardView.vue.
    -->
    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>