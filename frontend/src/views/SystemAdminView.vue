<!-- frontend/src/views/SystemAdminView.vue -->

<script setup>
import { onMounted, reactive, ref } from "vue";
import api from "../services/api.js";

const tabs = [
  { id: "overview", label: "系統總覽" },
  { id: "settings", label: "系統設定" },
];

const activeTab = ref("overview");

const overview = ref(null);
const settings = reactive({
  alert_warning_negative: 25,
  alert_critical_negative: 40,
  alert_min_articles: 5,
  auto_crawl_enabled: true,
  auto_crawl_hour: 3,
  auto_crawl_pages: 2,
});

const state = reactive({
  loadingOverview: false,
  loadingSettings: false,
  saving: false,
  message: "",
  messageType: "info",
});

function flash(text, type = "info") {
  state.message = text;
  state.messageType = type;
}

async function fetchOverview() {
  state.loadingOverview = true;
  try {
    const response = await api.get("/api/admin/system-overview");
    overview.value = response.data.data;
  } catch (error) {
    console.error(error);
    flash("系統總覽載入失敗。", "error");
  } finally {
    state.loadingOverview = false;
  }
}

async function fetchSettings() {
  state.loadingSettings = true;
  try {
    const response = await api.get("/api/admin/settings");
    Object.assign(settings, response.data.data);
  } catch (error) {
    console.error(error);
  } finally {
    state.loadingSettings = false;
  }
}

async function saveSettings() {
  if (state.saving) return;

  if (Number(settings.alert_warning_negative) >= Number(settings.alert_critical_negative)) {
    flash("警示門檻應小於危機門檻。", "error");
    return;
  }

  state.saving = true;
  try {
    const response = await api.put("/api/admin/settings", {
      alert_warning_negative: Number(settings.alert_warning_negative),
      alert_critical_negative: Number(settings.alert_critical_negative),
      alert_min_articles: Number(settings.alert_min_articles),
      auto_crawl_enabled: settings.auto_crawl_enabled,
      auto_crawl_hour: Number(settings.auto_crawl_hour),
      auto_crawl_pages: Number(settings.auto_crawl_pages),
    });
    Object.assign(settings, response.data.data);
    flash("設定已儲存。", "success");
  } catch (error) {
    console.error(error);
    flash(error.response?.status === 403 ? "只有管理員可修改設定。" : "儲存失敗，請稍後再試。", "error");
  } finally {
    state.saving = false;
  }
}

function formatTime(value) {
  if (!value) return "尚無紀錄";
  return new Intl.DateTimeFormat("zh-TW", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(value));
}

onMounted(() => {
  fetchOverview();
  fetchSettings();
});
</script>

<template>
  <section class="sysadmin-page">
    <div class="sysadmin-header">
      <h2>系統管理</h2>
      <p>檢視系統運作狀態，並調整預警門檻與自動爬取排程。</p>
    </div>

    <div class="sysadmin-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        :class="{ active: activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
    </div>

    <p v-if="state.message" :class="['sysadmin-message', state.messageType]">{{ state.message }}</p>

    <!-- 系統總覽 -->
    <div v-if="activeTab === 'overview'">
      <p v-if="state.loadingOverview" class="sysadmin-empty">載入中…</p>
      <div v-else-if="overview">
        <div class="sysadmin-stat-grid">
          <div class="sysadmin-stat">
            <span>資料庫</span>
            <strong :class="overview.database === 'connected' ? 'ok' : 'bad'">
              {{ overview.database === "connected" ? "正常連線" : "異常" }}
            </strong>
          </div>
          <div class="sysadmin-stat">
            <span>Gemini API</span>
            <strong :class="overview.gemini_configured ? 'ok' : 'bad'">
              {{ overview.gemini_configured ? "已設定" : "未設定" }}
            </strong>
          </div>
          <div class="sysadmin-stat">
            <span>文章總數</span>
            <strong>{{ overview.articles.total }}</strong>
          </div>
          <div class="sysadmin-stat">
            <span>AI 情緒覆蓋率</span>
            <strong>{{ overview.articles.rated_percent }}%</strong>
          </div>
          <div class="sysadmin-stat">
            <span>使用者</span>
            <strong>{{ overview.users.total }}（管理員 {{ overview.users.admins }}）</strong>
          </div>
          <div class="sysadmin-stat">
            <span>未讀預警</span>
            <strong :class="overview.monitor.unread_alerts ? 'warn' : ''">{{ overview.monitor.unread_alerts }}</strong>
          </div>
          <div class="sysadmin-stat">
            <span>自動排程</span>
            <strong :class="overview.scheduler.enabled ? 'ok' : ''">
              {{ overview.scheduler.enabled ? `每天 ${overview.scheduler.hour} 點` : "已停用" }}
            </strong>
          </div>
          <div class="sysadmin-stat">
            <span>最後爬取</span>
            <strong>{{ formatTime(overview.last_crawl.time) }}</strong>
          </div>
        </div>

        <article class="card sysadmin-board-card">
          <h3>各看板文章數</h3>
          <div class="sysadmin-board-grid">
            <div v-for="item in overview.articles.by_board" :key="item.board">
              <span>{{ item.board }}</span>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
        </article>
      </div>
    </div>

    <!-- 系統設定 -->
    <div v-else-if="activeTab === 'settings'">
      <article class="card sysadmin-settings-card">
        <h3>預警門檻</h3>
        <div class="sysadmin-field">
          <label>警示門檻（負面比例 ≥ %）</label>
          <input v-model.number="settings.alert_warning_negative" type="number" min="0" max="100" />
        </div>
        <div class="sysadmin-field">
          <label>危機門檻（負面比例 ≥ %）</label>
          <input v-model.number="settings.alert_critical_negative" type="number" min="0" max="100" />
        </div>
        <div class="sysadmin-field">
          <label>最少文章數（低於此數不預警）</label>
          <input v-model.number="settings.alert_min_articles" type="number" min="1" max="1000" />
        </div>
      </article>

      <article class="card sysadmin-settings-card">
        <h3>自動爬取排程</h3>
        <div class="sysadmin-field checkbox">
          <label>
            <input v-model="settings.auto_crawl_enabled" type="checkbox" />
            啟用每日自動爬取
          </label>
        </div>
        <div class="sysadmin-field">
          <label>執行時間（每天幾點，台灣時間）</label>
          <input v-model.number="settings.auto_crawl_hour" type="number" min="0" max="23" />
        </div>
        <div class="sysadmin-field">
          <label>每個看板爬取頁數</label>
          <input v-model.number="settings.auto_crawl_pages" type="number" min="1" max="20" />
        </div>
      </article>

      <button class="sysadmin-save" type="button" :disabled="state.saving" @click="saveSettings">
        {{ state.saving ? "儲存中…" : "儲存設定" }}
      </button>
    </div>
  </section>
</template>
