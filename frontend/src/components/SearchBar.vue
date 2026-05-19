<!-- frontend/src/components/SearchBar.vue -->

<script setup>
import { useDashboard } from "../composables/useDashboard.js";

const { state, searchDashboard } = useDashboard();


// Note:
// Khi user bấm nút search hoặc nhấn Enter,
// hàm này sẽ gọi API backend để reload dashboard.
function handleSubmit() {
  searchDashboard();
}
</script>

<template>
  <section class="card search-card">
    <div>
      <h2 class="section-title">搜尋條件</h2>
      <p class="section-desc">輸入關鍵字後，系統會查詢 Dashboard 資料與 LLM 洞察。</p>
    </div>

    <form class="search-form" @submit.prevent="handleSubmit">
      <div class="form-group">
        <label>關鍵字</label>

        <!-- Note:
          v-model 綁定 state.keyword。
          按 Enter 會觸發 form submit。
        -->
        <input
          v-model="state.keyword"
          type="text"
          placeholder="例如：玻尿酸、肉毒、保養"
        />
      </div>

      <div class="form-group">
        <label>看板</label>

        <!-- Note:
          board 先做 UI。
          如果 backend 之後支援 board filter，就可以把它傳給 API。
        -->
        <select v-model="state.board">
          <option value="all">全部版面</option>
          <option value="BeautySalon">BeautySalon</option>
          <option value="MakeUp">MakeUp</option>
          <option value="Skincare">Skincare</option>
        </select>
      </div>

      <div class="form-group">
        <label>時間範圍</label>

        <select v-model="state.days">
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
          <option :value="90">近 90 天</option>
        </select>
      </div>

      <button class="primary-button" type="submit">
        搜尋
      </button>
    </form>
  </section>
</template>