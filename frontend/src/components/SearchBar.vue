<!-- frontend/src/components/SearchBar.vue -->

<script setup>
import { ref } from "vue";
import { useDashboard } from "../composables/useDashboard.js";

const { state, searchDashboard } = useDashboard();

const keywordDraft = ref("");
const advancedOpen = ref(false);

const defaultKeywords = [
  "醫美",
  "整形",
  "玻尿酸",
  "肉毒",
  "雷射",
  "音波",
  "保養",
  "美白",
  "防曬",
  "A醇",
  "粉底",
  "口紅",
  "眼妝",
  "穿搭",
  "髮型",
  "痘痘",
  "美甲",
  "香水",
  "瘦身",
  "抗老",
  "保濕",
];

const recentKeywords = ref(["醫美", "A醇", "防曬", "混合肌"]);

const selectedKeywords = ref(
  state.keyword
    ? state.keyword
        .split(/[,\s、，]+/)
        .map((keyword) => keyword.trim())
        .filter(Boolean)
    : []
);

function addKeyword(keyword) {
  const value = keyword.trim();

  if (!value || selectedKeywords.value.includes(value)) {
    keywordDraft.value = "";
    return;
  }

  selectedKeywords.value = [...selectedKeywords.value, value];
  keywordDraft.value = "";
}

function removeKeyword(keyword) {
  selectedKeywords.value = selectedKeywords.value.filter((item) => item !== keyword);
}

function handleKeywordEnter() {
  addKeyword(keywordDraft.value);
}

function handleKeywordBackspace() {
  if (keywordDraft.value || selectedKeywords.value.length === 0) {
    return;
  }

  selectedKeywords.value = selectedKeywords.value.slice(0, -1);
}

function clearFilters() {
  selectedKeywords.value = [];
  keywordDraft.value = "";
}

function handleSubmit() {
  const keywords = [...selectedKeywords.value];
  const draft = keywordDraft.value.trim();

  if (draft && !keywords.includes(draft)) {
    keywords.push(draft);
  }

  state.keyword = keywords.join(" ");
  state.selectedBoards = [];
  selectedKeywords.value = keywords;
  keywordDraft.value = "";
  searchDashboard();
}
</script>

<template>
  <section class="search-conditions-card compact">
    <div class="search-conditions-header">
      <h2>搜尋條件</h2>
    </div>

    <form class="search-conditions-form" @submit.prevent="handleSubmit">
      <div class="compact-search-row">
        <div class="keyword-token-input">
          <button
            v-for="keyword in selectedKeywords"
            :key="keyword"
            class="keyword-token selected"
            type="button"
            @click="removeKeyword(keyword)"
          >
            {{ keyword }}
            <span>×</span>
          </button>

          <input
            v-model="keywordDraft"
            type="text"
            placeholder="輸入其他關鍵字後按 Enter 新增"
            @keydown.enter.prevent="handleKeywordEnter"
            @keydown.backspace="handleKeywordBackspace"
          />
        </div>

        <label class="days-select-label compact-days">
          <span>時間</span>
          <select v-model="state.days">
            <option :value="7">近 7 天</option>
            <option :value="30">近 30 天</option>
            <option :value="90">近 90 天</option>
          </select>
        </label>

        <button class="primary-button search-submit-button" type="submit">
          搜尋
        </button>

        <button
          class="secondary-button advanced-toggle-button"
          type="button"
          @click="advancedOpen = !advancedOpen"
        >
          {{ advancedOpen ? "收合" : "進階搜尋" }}
        </button>
      </div>

      <div class="hot-keyword-strip">
        <span>熱門關鍵字</span>
        <button
          v-for="keyword in defaultKeywords.slice(0, 8)"
          :key="keyword"
          class="keyword-preset compact"
          type="button"
          @click="addKeyword(keyword)"
        >
          {{ keyword }} ＋
        </button>
      </div>

      <div v-if="advancedOpen" class="condition-panel keyword-condition-panel">
        <div class="keyword-section">
          <span class="keyword-section-title">全部熱門關鍵字</span>
          <div class="keyword-preset-grid">
            <button
              v-for="keyword in defaultKeywords"
              :key="keyword"
              class="keyword-preset"
              type="button"
              @click="addKeyword(keyword)"
            >
              {{ keyword }}
              <span>＋</span>
            </button>
          </div>
        </div>

        <div class="keyword-section recent">
          <span class="keyword-section-title">最近使用</span>
          <div class="recent-keyword-row">
            <button
              v-for="keyword in recentKeywords"
              :key="keyword"
              class="keyword-token"
              type="button"
              @click="addKeyword(keyword)"
            >
              {{ keyword }}
              <span>×</span>
            </button>
          </div>
        </div>

        <button class="secondary-button clear-filter-button" type="button" @click="clearFilters">
          清除條件
        </button>
      </div>
    </form>
  </section>
</template>
