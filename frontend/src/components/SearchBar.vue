<!-- frontend/src/components/SearchBar.vue -->

<script setup>
import { computed } from "vue";
import { useDashboard } from "../composables/useDashboard.js";

const {
  state,
  targetBoards,
  searchDashboard,
} = useDashboard();

const allBoardsSelected = computed(
  () => state.selectedBoards.length === targetBoards.length
);

function handleSubmit() {
  searchDashboard();
}

function toggleAllBoards() {
  state.selectedBoards = allBoardsSelected.value
    ? []
    : targetBoards.map((board) => board.name);
}
</script>

<template>
  <section class="card search-card">
    <div>
      <h2 class="section-title">搜尋條件</h2>
      <p class="section-desc">輸入關鍵字後，系統會依照選取看板查詢 Dashboard 資料與 LLM 洞察。</p>
    </div>

    <form class="search-form" @submit.prevent="handleSubmit">
      <div class="form-group">
        <label>關鍵字</label>
        <input
          v-model="state.keyword"
          type="text"
          placeholder="例如：玻尿酸、肉毒、保養"
        />
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

    <div class="board-picker">
      <div class="board-picker-header">
        <strong>看板</strong>
        <button class="text-button" type="button" @click="toggleAllBoards">
          {{ allBoardsSelected ? "清除全部" : "選取全部" }}
        </button>
      </div>

      <div class="board-checkbox-grid">
        <label
          v-for="board in targetBoards"
          :key="board.name"
          class="board-checkbox"
        >
          <input
            v-model="state.selectedBoards"
            type="checkbox"
            :value="board.name"
          />
          <span>{{ board.label }}</span>
        </label>
      </div>

      <p class="board-hint">
        已選 {{ state.selectedBoards.length || targetBoards.length }} 個看板；若全部清除，系統會自動視為全選。
      </p>
    </div>
  </section>
</template>
