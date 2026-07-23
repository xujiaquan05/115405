<!-- frontend/src/components/AppNavbar.vue -->

<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../composables/useAuth";
import LogoMark from "./LogoMark.vue";

const router = useRouter();
const { state: authState, isAuthenticated, logout } = useAuth();

const isAdmin = computed(() => authState.user?.role === "admin");

function handleLogout() {
  logout();
  router.push("/login");
}

function goLogin() {
  router.push("/login");
}
</script>

<template>
  <header class="navbar">
    <RouterLink to="/dashboard" class="navbar-brand">
      <LogoMark :size="36" />
      <div>
        <span class="navbar-wordmark">MeBOD</span>
        <p class="navbar-subtitle">醫美時尚輿情分析系統</p>
      </div>
    </RouterLink>

    <nav class="navbar-links">
      <!-- RouterLink 用來切換頁面，不會重新載入整個網站。 -->
      <RouterLink to="/dashboard" class="nav-link">Dashboard</RouterLink>
      <RouterLink to="/qa" class="nav-link">AI 問答</RouterLink>
      <RouterLink to="/history" class="nav-link">History</RouterLink>
      <RouterLink v-if="isAdmin" to="/admin/users" class="nav-link">帳號管理</RouterLink>

      <div class="navbar-user">
        <template v-if="isAuthenticated">
          <RouterLink to="/profile" class="navbar-username navbar-username-link">
            {{ authState.user?.display_name || authState.user?.username }}
          </RouterLink>
          <button class="navbar-auth-button" type="button" @click="handleLogout">登出</button>
        </template>
        <template v-else>
          <span class="navbar-username">訪客</span>
          <button class="navbar-auth-button" type="button" @click="goLogin">登入</button>
        </template>
      </div>
    </nav>
  </header>
</template>
