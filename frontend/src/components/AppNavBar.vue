<!-- frontend/src/components/AppNavbar.vue -->

<script setup>
import { computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../composables/useAuth";
import { useAlerts } from "../composables/useAlerts";
import { useTheme } from "../composables/useTheme";
import LogoMark from "./LogoMark.vue";

const router = useRouter();
const { state: authState, isAuthenticated, logout } = useAuth();
const { state: alertState, fetchUnread } = useAlerts();
const { theme, toggleTheme } = useTheme();

const isAdmin = computed(() => authState.user?.role === "admin");

// 登入後抓取未讀預警數，顯示在 navbar 徽章。
function refreshAlertBadge() {
  if (isAuthenticated.value) fetchUnread();
}

onMounted(refreshAlertBadge);
watch(isAuthenticated, refreshAlertBadge);

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
    <RouterLink to="/" class="navbar-brand">
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
      <RouterLink v-if="isAuthenticated" to="/monitor" class="nav-link nav-link-alert">
        監控預警
        <span v-if="alertState.unreadCount" class="nav-alert-badge">{{ alertState.unreadCount }}</span>
      </RouterLink>
      <RouterLink v-if="isAdmin" to="/admin/users" class="nav-link">帳號管理</RouterLink>
      <RouterLink v-if="isAdmin" to="/admin/system" class="nav-link">系統管理</RouterLink>

      <button
        class="navbar-theme-toggle"
        type="button"
        :aria-label="theme === 'dark' ? '切換淺色模式' : '切換深色模式'"
        :title="theme === 'dark' ? '淺色模式' : '深色模式'"
        @click="toggleTheme"
      >
        <svg v-if="theme === 'dark'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="5" /><line x1="12" y1="1" x2="12" y2="3" /><line x1="12" y1="21" x2="12" y2="23" /><line x1="4.22" y1="4.22" x2="5.64" y2="5.64" /><line x1="18.36" y1="18.36" x2="19.78" y2="19.78" /><line x1="1" y1="12" x2="3" y2="12" /><line x1="21" y1="12" x2="23" y2="12" /><line x1="4.22" y1="19.78" x2="5.64" y2="18.36" /><line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      </button>

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
