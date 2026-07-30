<!-- frontend/src/views/MonitorView.vue -->

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import api from "../services/api.js";
import { useAuth } from "../composables/useAuth";
import { useAlerts } from "../composables/useAlerts";

const { state: authState } = useAuth();
const { fetchUnread } = useAlerts();

const isAdmin = computed(() => authState.user?.role === "admin");

const keywords = ref([]);
const alerts = ref([]);
const loading = reactive({ keywords: false, alerts: false, checking: false, running: false });
const message = reactive({ text: "", type: "info" });

const addForm = reactive({ keyword: "", days: 7 });

function flash(text, type = "info") {
  message.text = text;
  message.type = type;
}

async function fetchKeywords() {
  loading.keywords = true;
  try {
    const response = await api.get("/api/monitor/keywords");
    keywords.value = response.data.data.keywords;
  } catch (error) {
    console.error(error);
  } finally {
    loading.keywords = false;
  }
}

async function fetchAlerts() {
  loading.alerts = true;
  try {
    const response = await api.get("/api/monitor/alerts", { params: { limit: 50 } });
    alerts.value = response.data.data.alerts;
    fetchUnread();
  } catch (error) {
    console.error(error);
  } finally {
    loading.alerts = false;
  }
}

async function addKeyword() {
  const keyword = addForm.keyword.trim();
  if (!keyword) return;

  try {
    await api.post("/api/monitor/keywords", { keyword, days: addForm.days });
    addForm.keyword = "";
    flash(`已加入監控：「${keyword}」`, "success");
    await fetchKeywords();
  } catch (error) {
    console.error(error);
    flash(
      error.response?.status === 409 ? "此關鍵字已在監控清單中。"
      : error.response?.status === 401 ? "加入監控需要登入。"
      : "加入失敗，請稍後再試。",
      "error"
    );
  }
}

async function toggleKeyword(watch) {
  try {
    await api.patch(`/api/monitor/keywords/${watch.id}`, { enabled: !watch.enabled });
    await fetchKeywords();
  } catch (error) {
    console.error(error);
    flash("更新失敗。", "error");
  }
}

async function deleteKeyword(watch) {
  if (!window.confirm(`確定要移除監控「${watch.keyword}」嗎？`)) return;
  try {
    await api.delete(`/api/monitor/keywords/${watch.id}`);
    await fetchKeywords();
  } catch (error) {
    console.error(error);
    flash("移除失敗。", "error");
  }
}

async function checkNow() {
  if (loading.checking) return;
  loading.checking = true;
  try {
    const response = await api.post("/api/monitor/alerts/check");
    const count = response.data.created_count || 0;
    flash(count ? `檢查完成，新增 ${count} 筆預警。` : "檢查完成，目前沒有達到警戒的關鍵字。", "success");
    await fetchAlerts();
  } catch (error) {
    console.error(error);
    flash(error.response?.status === 401 ? "檢查需要登入。" : "檢查失敗，請稍後再試。", "error");
  } finally {
    loading.checking = false;
  }
}

async function markRead(alert) {
  try {
    await api.post(`/api/monitor/alerts/${alert.id}/read`);
    await fetchAlerts();
  } catch (error) {
    console.error(error);
  }
}

async function markAllRead() {
  try {
    await api.post("/api/monitor/alerts/read-all");
    await fetchAlerts();
  } catch (error) {
    console.error(error);
  }
}

async function runDailyNow() {
  if (loading.running) return;
  if (!window.confirm("確定要立即執行每日任務嗎？將爬取各看板、評分並檢查預警，可能需要數分鐘。")) return;
  loading.running = true;
  try {
    await api.post("/api/monitor/run-now");
    flash("每日任務已在背景開始執行，完成後可重新整理查看預警。", "success");
  } catch (error) {
    console.error(error);
    flash(error.response?.status === 403 ? "只有管理員可執行每日任務。" : "執行失敗。", "error");
  } finally {
    loading.running = false;
  }
}

function levelLabel(level) {
  return level === "critical" ? "危機" : "警示";
}

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-TW", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(value));
}

onMounted(() => {
  fetchKeywords();
  fetchAlerts();
});
</script>

<template>
  <section class="monitor-page">
    <div class="monitor-header">
      <h2>監控與預警</h2>
      <p>設定要長期追蹤的關鍵字，系統會定期分析並在負面聲量升高時主動預警。</p>
    </div>

    <p v-if="message.text" :class="['monitor-message', message.type]">{{ message.text }}</p>

    <div class="monitor-grid">
      <!-- 監控關鍵字 -->
      <article class="card monitor-card">
        <h3>監控關鍵字</h3>

        <form class="monitor-add-form" @submit.prevent="addKeyword">
          <input v-model="addForm.keyword" type="text" placeholder="輸入要監控的關鍵字" />
          <select v-model.number="addForm.days">
            <option :value="7">近 7 天</option>
            <option :value="30">近 30 天</option>
            <option :value="90">近 90 天</option>
          </select>
          <button type="submit">加入</button>
        </form>

        <p v-if="!keywords.length" class="monitor-empty">尚未設定監控關鍵字。</p>
        <ul v-else class="monitor-keyword-list">
          <li v-for="watch in keywords" :key="watch.id">
            <div>
              <strong>{{ watch.keyword }}</strong>
              <small>近 {{ watch.days }} 天</small>
            </div>
            <div class="monitor-keyword-actions">
              <button
                type="button"
                :class="['monitor-toggle', watch.enabled ? 'on' : 'off']"
                @click="toggleKeyword(watch)"
              >
                {{ watch.enabled ? "監控中" : "已暫停" }}
              </button>
              <button type="button" class="monitor-delete" @click="deleteKeyword(watch)">移除</button>
            </div>
          </li>
        </ul>
      </article>

      <!-- 預警 -->
      <article class="card monitor-card">
        <div class="monitor-alert-head">
          <h3>風險預警</h3>
          <div class="monitor-alert-actions">
            <button type="button" class="monitor-primary" :disabled="loading.checking" @click="checkNow">
              {{ loading.checking ? "檢查中…" : "立即檢查" }}
            </button>
            <button type="button" class="monitor-ghost" @click="markAllRead">全部已讀</button>
            <button v-if="isAdmin" type="button" class="monitor-ghost" :disabled="loading.running" @click="runDailyNow">
              {{ loading.running ? "執行中…" : "執行每日任務" }}
            </button>
          </div>
        </div>

        <p v-if="!alerts.length" class="monitor-empty">目前沒有預警。設定關鍵字後按「立即檢查」試試。</p>
        <ul v-else class="monitor-alert-list">
          <li
            v-for="alert in alerts"
            :key="alert.id"
            :class="['monitor-alert-item', alert.level, { read: alert.is_read }]"
          >
            <div class="monitor-alert-top">
              <span :class="['monitor-alert-badge', alert.level]">{{ levelLabel(alert.level) }}</span>
              <strong>{{ alert.title }}</strong>
              <span v-if="!alert.is_read" class="monitor-unread-dot" aria-label="未讀"></span>
            </div>
            <p class="monitor-alert-detail">{{ alert.detail }}</p>
            <div class="monitor-alert-foot">
              <span>{{ formatDate(alert.created_at) }}</span>
              <button v-if="!alert.is_read" type="button" @click="markRead(alert)">標為已讀</button>
            </div>
          </li>
        </ul>
      </article>
    </div>
  </section>
</template>
