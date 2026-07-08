<!-- frontend/src/components/AppNavbar.vue -->

<template>
  <header class="navbar">
    <div>
      <h1 class="navbar-title">醫美時尚輿情分析系統</h1>
      <p class="navbar-subtitle">Medical Beauty Opinion Dashboard</p>
    </div>

    <nav class="navbar-links">
      <!-- RouterLink 用來切換頁面，不會重新載入整個網站。 -->
      <RouterLink to="/" class="nav-link">Dashboard</RouterLink>
      <RouterLink to="/qa" class="nav-link">AI 問答</RouterLink>
      <RouterLink to="/history" class="nav-link">History</RouterLink>
    </nav>
  </header>
</template>
