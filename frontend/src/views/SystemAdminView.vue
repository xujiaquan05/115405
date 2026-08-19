<!-- frontend/src/views/SystemAdminView.vue -->

<script setup>
import { onMounted, reactive, ref } from "vue";
import api from "../services/api.js";

const tabs = [
  { id: "overview", label: "系統總覽" },
  { id: "settings", label: "系統設定" },
  { id: "boards", label: "看板管理" },
  { id: "audit", label: "操作紀錄" },
];

const activeTab = ref("overview");

// 看板管理
const boards = ref([]);
const newBoard = reactive({ name: "", display_name: "", platform: "ptt" });
const PLATFORM_LABELS = { ptt: "PTT", dcard: "Dcard", mobile01: "Mobile01" };
function platformLabel(name) {
  return PLATFORM_LABELS[name] || name;
}

// 操作紀錄
const auditLogs = ref([]);
const auditFilter = ref("all");
const AUDIT_ACTIONS = [
  { value: "all", label: "全部操作" },
  { value: "create_user", label: "建立帳號" },
  { value: "update_user", label: "修改帳號" },
  { value: "delete_user", label: "刪除帳號" },
  { value: "update_settings", label: "修改設定" },
  { value: "create_board", label: "新增看板" },
  { value: "update_board", label: "調整看板" },
  { value: "delete_board", label: "刪除看板" },
  { value: "trigger_crawl", label: "觸發爬取" },
  { value: "reset_crawl", label: "重置爬取" },
  { value: "refresh_sentiment", label: "重新評分" },
  { value: "add_watch_keyword", label: "新增監控" },
  { value: "delete_watch_keyword", label: "移除監控" },
  { value: "delete_history", label: "刪除紀錄" },
];

function auditActionLabel(action) {
  return AUDIT_ACTIONS.find((a) => a.value === action)?.label || action;
}

const overview = ref(null);
const settings = reactive({
  alert_warning_negative: 25,
  alert_critical_negative: 40,
  alert_min_articles: 5,
  auto_crawl_enabled: true,
  auto_crawl_hour: 3,
  auto_crawl_pages: 2,
  dcard_crawl_enabled: true,
  mobile01_crawl_enabled: true,
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
      dcard_crawl_enabled: settings.dcard_crawl_enabled,
      mobile01_crawl_enabled: settings.mobile01_crawl_enabled,
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

// ── 看板管理 ──
async function fetchBoards() {
  try {
    const response = await api.get("/api/admin/boards");
    boards.value = response.data.data.boards;
  } catch (error) {
    console.error(error);
    flash("看板列表載入失敗。", "error");
  }
}

async function addBoard() {
  const name = newBoard.name.trim();
  if (!name) return;
  try {
    await api.post("/api/admin/boards", {
      name,
      display_name: newBoard.display_name.trim() || null,
      platform: newBoard.platform,
    });
    newBoard.name = "";
    newBoard.display_name = "";
    flash(`已新增看板「${name}」。`, "success");
    await fetchBoards();
  } catch (error) {
    console.error(error);
    flash(error.response?.status === 409 ? "此看板已存在。" : "新增失敗。", "error");
  }
}

async function toggleBoard(board) {
  try {
    await api.patch(`/api/admin/boards/${board.id}`, { is_active: !board.is_active });
    await fetchBoards();
  } catch (error) {
    console.error(error);
    flash("更新失敗。", "error");
  }
}

async function deleteBoard(board) {
  if (!window.confirm(`確定要刪除看板「${board.name}」嗎？`)) return;
  try {
    await api.delete(`/api/admin/boards/${board.id}`);
    flash(`已刪除看板「${board.name}」。`, "success");
    await fetchBoards();
  } catch (error) {
    console.error(error);
    flash(error.response?.status === 409 ? error.response.data.detail : "刪除失敗。", "error");
  }
}

// ── 操作紀錄 ──
async function fetchAudit() {
  try {
    const params = { limit: 100 };
    if (auditFilter.value !== "all") params.action = auditFilter.value;
    const response = await api.get("/api/admin/audit-logs", { params });
    auditLogs.value = response.data.data.logs;
  } catch (error) {
    console.error(error);
  }
}

function switchTab(id) {
  activeTab.value = id;
  if (id === "boards" && !boards.value.length) fetchBoards();
  if (id === "audit") fetchAudit();
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
        @click="switchTab(tab.id)"
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
        <div class="sysadmin-field checkbox">
          <label>
            <input v-model="settings.dcard_crawl_enabled" type="checkbox" />
            啟用 Dcard 爬取（需伺服器可執行瀏覽器；無頭環境請關閉）
          </label>
        </div>
        <div class="sysadmin-field checkbox">
          <label>
            <input v-model="settings.mobile01_crawl_enabled" type="checkbox" />
            啟用 Mobile01 爬取（需伺服器可執行瀏覽器；無頭環境請關閉）
          </label>
        </div>
      </article>

      <button class="sysadmin-save" type="button" :disabled="state.saving" @click="saveSettings">
        {{ state.saving ? "儲存中…" : "儲存設定" }}
      </button>
    </div>

    <!-- 看板管理 -->
    <div v-else-if="activeTab === 'boards'">
      <article class="card sysadmin-settings-card">
        <h3>新增看板</h3>
        <p class="sysadmin-hint">
          看板代號需與網址一致：PTT 例如 <code>BeautySalon</code>、<code>MakeUp</code>；
          Dcard 例如 <code>facelift</code>（醫美）、<code>makeup</code>（美妝）、<code>dressup</code>（穿搭）；
          Mobile01 用討論區編號，例如 <code>371</code>（彩妝保養）、<code>373</code>（時尚流行）。
          停用的看板不會納入每日自動爬取。
        </p>
        <div class="sysadmin-board-form">
          <select v-model="newBoard.platform" class="sysadmin-platform-select">
            <option value="ptt">PTT</option>
            <option value="dcard">Dcard</option>
            <option value="mobile01">Mobile01</option>
          </select>
          <input v-model="newBoard.name" type="text" placeholder="看板代號（board / forum alias）" />
          <input v-model="newBoard.display_name" type="text" placeholder="顯示名稱（選填）" />
          <button type="button" :disabled="!newBoard.name.trim()" @click="addBoard">新增</button>
        </div>
      </article>

      <article class="card sysadmin-settings-card">
        <h3>看板清單</h3>
        <p v-if="!boards.length" class="sysadmin-empty">尚無看板資料。</p>
        <table v-else class="sysadmin-table">
          <thead>
            <tr>
              <th>平台</th>
              <th>看板</th>
              <th>顯示名稱</th>
              <th>文章數</th>
              <th>狀態</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="board in boards" :key="board.id">
              <td><span class="sysadmin-badge platform">{{ platformLabel(board.platform) }}</span></td>
              <td>{{ board.name }}</td>
              <td>{{ board.display_name || "—" }}</td>
              <td>{{ board.article_count }}</td>
              <td>
                <span :class="['sysadmin-badge', board.is_active ? 'on' : 'off']">
                  {{ board.is_active ? "爬取中" : "已停用" }}
                </span>
              </td>
              <td class="sysadmin-actions">
                <button type="button" class="link" @click="toggleBoard(board)">
                  {{ board.is_active ? "停用" : "啟用" }}
                </button>
                <button type="button" class="link danger" @click="deleteBoard(board)">刪除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </article>
    </div>

    <!-- 操作紀錄 -->
    <div v-else-if="activeTab === 'audit'">
      <article class="card sysadmin-settings-card">
        <div class="sysadmin-audit-head">
          <h3>操作紀錄</h3>
          <select v-model="auditFilter" @change="fetchAudit">
            <option v-for="opt in AUDIT_ACTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
        <p v-if="!auditLogs.length" class="sysadmin-empty">沒有符合條件的紀錄。</p>
        <table v-else class="sysadmin-table">
          <thead>
            <tr>
              <th>時間</th>
              <th>操作者</th>
              <th>動作</th>
              <th>內容</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in auditLogs" :key="log.id">
              <td>{{ formatTime(log.created_at) }}</td>
              <td>{{ log.actor_username || "系統" }}</td>
              <td><span class="sysadmin-badge">{{ auditActionLabel(log.action) }}</span></td>
              <td>{{ log.detail || "—" }}</td>
            </tr>
          </tbody>
        </table>
      </article>
    </div>
  </section>
</template>
