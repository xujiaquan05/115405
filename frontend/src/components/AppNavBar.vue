<!-- frontend/src/components/AppNavbar.vue -->

<template>
  <header class="navbar">
    <div>
      <h1 class="navbar-title">醫美時尚輿情分析系統</h1>
      <p class="navbar-subtitle">Medical Beauty Opinion Dashboard</p>
    </div>

    <nav class="navbar-links">
      <!-- Note:
        RouterLink dùng để chuyển trang mà không reload toàn bộ website.
      -->
      <RouterLink to="/" class="nav-link">Dashboard</RouterLink>
      <RouterLink to="/qa" class="nav-link">AI 問答</RouterLink>
      <RouterLink to="/crawl" class="nav-link">爬蟲管理</RouterLink>
      <RouterLink to="/history" class="nav-link">History</RouterLink>
    </nav>
  </header>
</template>
