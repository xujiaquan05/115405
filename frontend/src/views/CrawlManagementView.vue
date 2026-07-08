<!-- frontend/src/views/CrawlManagementView.vue -->

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import api from "../services/api.js";
import { useWebSocket } from "../composables/useWebSocket.js";

const boards = [
  { name: "facelift", label: "facelift 醫美整形" },
  { name: "BeautySalon", label: "BeautySalon 醫美板" },
  { name: "MakeUp", label: "MakeUp 彩妝保養板" },
  { name: "Mix_Match", label: "Mix_Match 穿搭板" },
  { name: "fashion", label: "fashion 時尚板" },
  { name: "Brand", label: "Brand 精品品牌板" },
  { name: "e-shopping", label: "e-shopping 網購板" },
  { name: "NailSalon", label: "NailSalon 美甲板" },
  { name: "Mancare", label: "Mancare 男性保養板" },
  { name: "teeth_salon", label: "teeth_salon 牙齒美容板" },
];

const pageSizeOptions = [10, 20, 50];

const {
  state: websocketState,
  connect,
} = useWebSocket();

const form = reactive({
  board: "BeautySalon",
  pages: 5,
  range: "latest",
});

const state = reactive({
  loading: false,
  refreshing: false,
  errorMessage: "",
  summary: {},
  logs: [],
  boardCounts: [],
});

const statusFilter = ref("all");
const currentPage = ref(1);
const pageSize = ref(10);

const filteredLogs = computed(() => {
  if (statusFilter.value === "all") {
    return state.logs;
  }

  return state.logs.filter((log) => log.status === statusFilter.value);
});

const totalPages = computed(() => {
  return Math.max(1, Math.ceil(filteredLogs.value.length / pageSize.value));
});

const pagedLogs = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return filteredLogs.value.slice(start, start + pageSize.value);
});

const selectedBoardLabel = computed(() => {
  return boards.find((board) => board.name === form.board)?.label || form.board;
});

const runningProgress = computed(() => {
  if (websocketState.crawler.status !== "running") {
    return state.summary.status === "running" ? 12 : 0;
  }

  return websocketState.crawler.progress || 0;
});

const progressPercent = computed(() => {
  return Math.min(100, Math.max(0, Math.round(runningProgress.value)));
});

const isRunning = computed(() => {
  return state.loading || websocketState.crawler.status === "running" || state.summary.status === "running";
});

function formatDateTime(value) {
  if (!value) return "-";

  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatShortDateTime(value) {
  if (!value) return "-";

  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatDuration(seconds) {
  if (!seconds && seconds !== 0) return "-";

  const minutes = Math.floor(seconds / 60);
  const restSeconds = seconds % 60;

  return `${String(minutes).padStart(2, "0")}:${String(restSeconds).padStart(2, "0")}`;
}

function getStatusText(status) {
  const labels = {
    running: "執行中",
    success: "成功",
    failed: "失敗",
    completed: "成功",
    idle: "閒置中",
  };

  return labels[status] || status || "-";
}

function getStatusClass(status) {
  if (status === "success" || status === "completed") return "success";
  if (status === "failed") return "failed";
  if (status === "running") return "running";
  return "idle";
}

async function fetchCrawlerStatus() {
  state.refreshing = true;
  state.errorMessage = "";

  try {
    const response = await api.get("/api/crawler/status", {
      params: { limit: 100 },
    });

    const data = response.data.data || {};
    state.summary = data.summary || {};
    state.logs = data.logs || [];
    state.boardCounts = data.board_counts || [];
    currentPage.value = Math.min(currentPage.value, totalPages.value);
  } catch (error) {
    console.error(error);
    state.errorMessage = "爬蟲狀態載入失敗，請確認 backend 是否正在執行。";
  } finally {
    state.refreshing = false;
  }
}

async function startCrawler() {
  if (isRunning.value) return;

  state.loading = true;
  state.errorMessage = "";
  form.pages = Math.max(1, Number(form.pages) || 1);

  try {
    await api.post("/api/crawler/ptt", null, {
      params: {
        board: form.board,
        pages: form.pages,
      },
    });

    await fetchCrawlerStatus();
  } catch (error) {
    console.error(error);
    state.errorMessage = error.response?.status === 409
      ? "已有爬取任務執行中，請等待目前任務完成後再試。"
      : "啟動爬蟲失敗，請確認網路、PTT 連線或 backend log。";
  } finally {
    state.loading = false;
  }
}

function changeStatusFilter(event) {
  statusFilter.value = event.target.value;
  currentPage.value = 1;
}

function changePageSize(event) {
  pageSize.value = Number(event.target.value);
  currentPage.value = 1;
}

onMounted(() => {
  connect();
  fetchCrawlerStatus();
});
</script>

<template>
  <section class="crawl-page">
    <div class="crawl-page-header">
      <h2>爬蟲管理</h2>
      <p>管理 PTT 看板資料爬取、即時進度與執行紀錄。</p>
    </div>

    <p v-if="state.errorMessage" class="error-message">
      {{ state.errorMessage }}
    </p>

    <div class="crawler-stat-grid">
      <article class="crawler-stat-card">
        <div>
          <span class="crawler-stat-label">執行狀態</span>
          <strong :class="['crawler-status-pill', getStatusClass(isRunning ? 'running' : state.summary.status)]">
            {{ getStatusText(isRunning ? "running" : state.summary.status) }}
          </strong>
          <small>{{ isRunning ? "目前有爬取任務正在執行中" : "目前沒有爬取任務執行中" }}</small>
        </div>
        <span class="crawler-stat-icon green">⌁</span>
      </article>

      <article class="crawler-stat-card">
        <div>
          <span class="crawler-stat-label">上次爬取時間</span>
          <strong>{{ formatShortDateTime(state.summary.last_crawled_at) }}</strong>
          <small>{{ state.summary.last_crawled_ago ? `距離現在 ${state.summary.last_crawled_ago}` : "尚無紀錄" }}</small>
        </div>
        <span class="crawler-stat-icon blue">◷</span>
      </article>

      <article class="crawler-stat-card">
        <div>
          <span class="crawler-stat-label">本次新增文章數</span>
          <strong class="crawler-stat-number green-text">
            {{ websocketState.crawler.newCount || state.summary.today_new_count || 0 }}
          </strong>
          <small>今日新增文章統計</small>
        </div>
        <span class="crawler-stat-icon green">▣</span>
      </article>

      <article class="crawler-stat-card">
        <div>
          <span class="crawler-stat-label">本次跳過重複數</span>
          <strong class="crawler-stat-number orange-text">
            {{ websocketState.crawler.skippedCount || state.summary.today_skipped_count || 0 }}
          </strong>
          <small>重複文章自動略過</small>
        </div>
        <span class="crawler-stat-icon orange">▤</span>
      </article>
    </div>

    <div class="crawler-work-grid">
      <section class="crawler-panel">
        <h3>手動爬取</h3>
        <p>選擇看板與爬取範圍後立即開始爬取任務。</p>

        <form class="crawler-form" @submit.prevent="startCrawler">
          <label>
            <span>看板選擇</span>
            <select v-model="form.board">
              <option
                v-for="board in boards"
                :key="board.name"
                :value="board.name"
              >
                {{ board.label }}
              </option>
            </select>
          </label>

          <label>
            <span>爬取頁數</span>
            <input
              v-model.number="form.pages"
              type="number"
              min="1"
              step="1"
              inputmode="numeric"
              placeholder="例如：45"
            />
          </label>

          <label>
            <span>時間範圍</span>
            <select v-model="form.range">
              <option value="latest">最新文章</option>
            </select>
          </label>

          <button class="crawler-primary-button" type="submit" :disabled="isRunning">
            <span>▶</span>
            {{ isRunning ? "爬取中" : "開始爬取" }}
          </button>
        </form>

        <div class="crawler-tip">
          可自行輸入要爬取的頁數，系統會依照你填寫的數量執行。
        </div>
      </section>

      <section class="crawler-panel">
        <div class="crawler-panel-header">
          <div>
            <h3>即時進度</h3>
            <strong :class="['crawler-status-pill', getStatusClass(isRunning ? 'running' : state.summary.status)]">
              {{ getStatusText(isRunning ? "running" : state.summary.status) }}
            </strong>
          </div>
          <span>開始時間：{{ formatDateTime(state.summary.running_started_at) }}</span>
        </div>

        <p class="crawler-current-board">
          看板：{{ websocketState.crawler.board || state.summary.running_board || selectedBoardLabel }}
        </p>

        <div class="crawler-progress-line">
          <div class="crawler-progress-track">
            <div class="crawler-progress-bar" :style="{ width: `${progressPercent}%` }"></div>
          </div>
          <strong>{{ progressPercent }}%</strong>
        </div>

        <div class="crawler-progress-stats">
          <div>
            <span>目前頁數</span>
            <strong>{{ websocketState.crawler.currentPage || 0 }} / {{ websocketState.crawler.totalPages || form.pages }} 頁</strong>
          </div>
          <div>
            <span>新增文章數</span>
            <strong>{{ websocketState.crawler.newCount || 0 }} 篇</strong>
          </div>
          <div>
            <span>跳過重複數</span>
            <strong>{{ websocketState.crawler.skippedCount || 0 }} 篇</strong>
          </div>
          <div>
            <span>預估剩餘時間</span>
            <strong>{{ isRunning ? "計算中" : "00:00" }}</strong>
          </div>
        </div>
      </section>
    </div>

    <section class="crawler-log-card">
      <div class="crawler-log-header">
        <h3>爬蟲執行紀錄</h3>

        <div class="crawler-log-actions">
          <button class="crawler-ghost-button" type="button" @click="fetchCrawlerStatus">
            ⟳ 重新整理
          </button>
          <select :value="statusFilter" @change="changeStatusFilter">
            <option value="all">全部狀態</option>
            <option value="running">執行中</option>
            <option value="success">成功</option>
            <option value="failed">失敗</option>
          </select>
        </div>
      </div>

      <div class="crawler-log-table-wrap">
        <table class="crawler-log-table">
          <thead>
            <tr>
              <th>時間</th>
              <th>看板</th>
              <th>狀態</th>
              <th>爬取頁數</th>
              <th>新增文章數</th>
              <th>跳過重複數</th>
              <th>錯誤訊息</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in pagedLogs" :key="log.id">
              <td>{{ formatDateTime(log.time) }}</td>
              <td>{{ log.board }}</td>
              <td>
                <span :class="['crawler-status-pill', getStatusClass(log.status)]">
                  {{ getStatusText(log.status) }}
                </span>
              </td>
              <td>{{ log.pages || "-" }}</td>
              <td>{{ log.new_count }}</td>
              <td>{{ log.skipped_count }}</td>
              <td :class="{ 'crawler-error-text': log.error_message }">
                {{ log.error_message || "-" }}
              </td>
              <td>
                <button class="crawler-outline-button" type="button">
                  檢視
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="!pagedLogs.length" class="empty-state">
          目前尚無爬蟲執行紀錄。
        </div>
      </div>

      <div class="crawler-pagination">
        <div>
          <button
            class="crawler-page-button"
            type="button"
            :disabled="currentPage === 1"
            @click="currentPage -= 1"
          >
            ‹
          </button>
          <button class="crawler-page-button active" type="button">
            {{ currentPage }}
          </button>
          <button
            class="crawler-page-button"
            type="button"
            :disabled="currentPage === totalPages"
            @click="currentPage += 1"
          >
            ›
          </button>
        </div>

        <div class="crawler-page-size">
          <span>每頁顯示</span>
          <select :value="pageSize" @change="changePageSize">
            <option
              v-for="size in pageSizeOptions"
              :key="size"
              :value="size"
            >
              {{ size }}
            </option>
          </select>
          <span>共 {{ filteredLogs.length }} 筆</span>
        </div>
      </div>
    </section>
  </section>
</template>
