<!-- frontend/src/views/AdminUsersView.vue -->

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useAuth } from "../composables/useAuth";
import api from "../services/api";

const { state: authState } = useAuth();
const currentUserId = computed(() => authState.user?.id);

const users = ref([]);
const stats = ref({ total: 0, admins: 0, active: 0, logged_this_week: 0 });
const auditLogs = ref([]);
const loading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

// 搜尋與篩選
const searchText = ref("");
const roleFilter = ref("all");
const statusFilter = ref("all");

// 分頁
const currentPage = ref(1);
const pageSize = 8;

const createForm = reactive({
  username: "",
  display_name: "",
  password: "",
  role: "user",
  submitting: false,
});

// 編輯 modal
const editModal = reactive({
  open: false,
  userId: null,
  username: "",
  display_name: "",
  role: "user",
  is_active: true,
  new_password: "",
  submitting: false,
  isSelf: false,
});

function flashSuccess(message) {
  successMessage.value = message;
  errorMessage.value = "";
}

function flashError(error, fallback) {
  errorMessage.value = error.response?.data?.detail || fallback;
  successMessage.value = "";
}

const filteredUsers = computed(() => {
  const keyword = searchText.value.trim().toLowerCase();

  return users.value.filter((user) => {
    const matchKeyword =
      !keyword ||
      user.username.toLowerCase().includes(keyword) ||
      (user.display_name || "").toLowerCase().includes(keyword);
    const matchRole = roleFilter.value === "all" || user.role === roleFilter.value;
    const matchStatus =
      statusFilter.value === "all" ||
      (statusFilter.value === "active" ? user.is_active : !user.is_active);

    return matchKeyword && matchRole && matchStatus;
  });
});

const totalPages = computed(() => Math.max(1, Math.ceil(filteredUsers.value.length / pageSize)));

const pagedUsers = computed(() => {
  const page = Math.min(currentPage.value, totalPages.value);
  const start = (page - 1) * pageSize;
  return filteredUsers.value.slice(start, start + pageSize);
});

function resetToFirstPage() {
  currentPage.value = 1;
}

async function fetchUsers() {
  loading.value = true;
  errorMessage.value = "";

  try {
    const response = await api.get("/api/admin/users");
    users.value = response.data.data.users;
    stats.value = response.data.data.stats;
  } catch (error) {
    console.error(error);
    flashError(error, "載入使用者清單失敗。");
  } finally {
    loading.value = false;
  }
}

async function fetchAuditLogs() {
  try {
    const response = await api.get("/api/admin/audit-logs", { params: { limit: 20 } });
    auditLogs.value = response.data.data.logs;
  } catch (error) {
    console.error(error);
  }
}

async function refreshAll() {
  await Promise.all([fetchUsers(), fetchAuditLogs()]);
}

async function createUser() {
  if (createForm.submitting) return;

  if (!createForm.username.trim() || createForm.password.length < 6) {
    flashError({}, "請輸入帳號，且密碼至少 6 個字元。");
    return;
  }

  createForm.submitting = true;

  try {
    await api.post("/api/admin/users", {
      username: createForm.username.trim(),
      display_name: createForm.display_name.trim() || null,
      password: createForm.password,
      role: createForm.role,
    });

    flashSuccess(`已建立帳號「${createForm.username.trim()}」。`);
    createForm.username = "";
    createForm.display_name = "";
    createForm.password = "";
    createForm.role = "user";
    await refreshAll();
  } catch (error) {
    console.error(error);
    flashError(error, "建立帳號失敗。");
  } finally {
    createForm.submitting = false;
  }
}

function openEdit(user) {
  editModal.open = true;
  editModal.userId = user.id;
  editModal.username = user.username;
  editModal.display_name = user.display_name;
  editModal.role = user.role;
  editModal.is_active = Boolean(user.is_active);
  editModal.new_password = "";
  editModal.isSelf = user.id === currentUserId.value;
}

function closeEdit() {
  editModal.open = false;
}

async function submitEdit() {
  if (editModal.submitting) return;

  if (editModal.new_password && editModal.new_password.length < 6) {
    flashError({}, "新密碼至少需要 6 個字元。");
    return;
  }

  editModal.submitting = true;

  const payload = {
    display_name: editModal.display_name,
    role: editModal.role,
    is_active: editModal.is_active,
  };
  if (editModal.new_password) payload.new_password = editModal.new_password;

  try {
    await api.patch(`/api/admin/users/${editModal.userId}`, payload);
    flashSuccess(`已更新帳號「${editModal.username}」。`);
    editModal.open = false;
    await refreshAll();
  } catch (error) {
    console.error(error);
    flashError(error, "更新失敗。");
  } finally {
    editModal.submitting = false;
  }
}

async function deleteUser(user) {
  if (!window.confirm(`確定要刪除帳號「${user.username}」嗎？此動作無法復原。`)) return;

  try {
    await api.delete(`/api/admin/users/${user.id}`);
    flashSuccess(`已刪除帳號「${user.username}」。`);
    await refreshAll();
  } catch (error) {
    console.error(error);
    flashError(error, "刪除失敗。");
  }
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("zh-TW");
}

function formatRelative(value) {
  if (!value) return "從未登入";

  const diffMs = Date.now() - new Date(value).getTime();
  const minutes = Math.floor(diffMs / 60000);

  if (minutes < 1) return "剛剛";
  if (minutes < 60) return `${minutes} 分鐘前`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小時前`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;

  return formatDate(value);
}

onMounted(refreshAll);
</script>

<template>
  <section class="admin-page">
    <div class="admin-page-header">
      <h2>帳號管理</h2>
      <p>建立、搜尋與管理系統使用者，並檢視後台操作紀錄。</p>
    </div>

    <p v-if="errorMessage" class="admin-message error">{{ errorMessage }}</p>
    <p v-if="successMessage" class="admin-message success">{{ successMessage }}</p>

    <!-- 統計卡片 -->
    <div class="admin-stat-grid">
      <div class="admin-stat-card">
        <span class="admin-stat-label">總帳號數</span>
        <strong class="admin-stat-value">{{ stats.total }}</strong>
      </div>
      <div class="admin-stat-card">
        <span class="admin-stat-label">管理員</span>
        <strong class="admin-stat-value indigo">{{ stats.admins }}</strong>
      </div>
      <div class="admin-stat-card">
        <span class="admin-stat-label">啟用中</span>
        <strong class="admin-stat-value green">{{ stats.active }}</strong>
      </div>
      <div class="admin-stat-card">
        <span class="admin-stat-label">本週登入</span>
        <strong class="admin-stat-value">{{ stats.logged_this_week }}</strong>
      </div>
    </div>

    <!-- 新增帳號 -->
    <article class="card admin-create-card">
      <h3>新增帳號</h3>
      <form class="admin-create-form" @submit.prevent="createUser">
        <label>
          <span>帳號</span>
          <input v-model="createForm.username" type="text" autocomplete="off" placeholder="登入用帳號" />
        </label>
        <label>
          <span>顯示名稱</span>
          <input v-model="createForm.display_name" type="text" autocomplete="off" placeholder="選填" />
        </label>
        <label>
          <span>密碼（至少 6 字元）</span>
          <input v-model="createForm.password" type="password" autocomplete="new-password" />
        </label>
        <label>
          <span>角色</span>
          <select v-model="createForm.role">
            <option value="user">一般使用者</option>
            <option value="admin">管理員</option>
          </select>
        </label>
        <button type="submit" :disabled="createForm.submitting">
          {{ createForm.submitting ? "建立中…" : "建立帳號" }}
        </button>
      </form>
    </article>

    <!-- 使用者清單 -->
    <article class="card admin-list-card">
      <div class="admin-list-header">
        <h3>使用者清單</h3>
        <button class="admin-ghost-button" type="button" @click="refreshAll">⟳ 重新整理</button>
      </div>

      <div class="admin-toolbar">
        <input
          v-model="searchText"
          class="admin-search"
          type="text"
          placeholder="🔍 搜尋帳號或顯示名稱"
          @input="resetToFirstPage"
        />
        <select v-model="roleFilter" @change="resetToFirstPage">
          <option value="all">全部角色</option>
          <option value="admin">管理員</option>
          <option value="user">一般使用者</option>
        </select>
        <select v-model="statusFilter" @change="resetToFirstPage">
          <option value="all">全部狀態</option>
          <option value="active">啟用中</option>
          <option value="inactive">已停用</option>
        </select>
      </div>

      <p v-if="loading" class="admin-empty">載入中…</p>
      <p v-else-if="!filteredUsers.length" class="admin-empty">沒有符合條件的使用者。</p>

      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>帳號</th>
              <th>角色</th>
              <th>狀態</th>
              <th>最後登入</th>
              <th>建立日期</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in pagedUsers" :key="user.id">
              <td>
                <strong>{{ user.username }}</strong>
                <span v-if="user.id === currentUserId" class="admin-self-tag">你</span>
                <div class="admin-sub">{{ user.display_name }}</div>
              </td>
              <td>
                <span :class="['admin-role-badge', user.role === 'admin' ? 'is-admin' : '']">
                  {{ user.role === "admin" ? "管理員" : "一般使用者" }}
                </span>
              </td>
              <td>
                <span :class="['admin-status-dot', user.is_active ? 'is-active' : 'is-inactive']">
                  ● {{ user.is_active ? "啟用中" : "已停用" }}
                </span>
              </td>
              <td>{{ formatRelative(user.last_login_at) }}</td>
              <td>{{ formatDate(user.created_at) }}</td>
              <td>
                <div class="admin-actions">
                  <button type="button" @click="openEdit(user)">✎ 編輯</button>
                  <button
                    type="button"
                    class="admin-danger"
                    @click="deleteUser(user)"
                    :disabled="user.id === currentUserId"
                  >
                    刪除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="totalPages > 1" class="admin-pagination">
        <button type="button" :disabled="currentPage <= 1" @click="currentPage--">上一頁</button>
        <span>第 {{ currentPage }} / {{ totalPages }} 頁</span>
        <button type="button" :disabled="currentPage >= totalPages" @click="currentPage++">下一頁</button>
      </div>
    </article>

    <!-- 操作紀錄 -->
    <article class="card admin-audit-card">
      <h3>操作紀錄（稽核 log）</h3>
      <p v-if="!auditLogs.length" class="admin-empty">尚無操作紀錄。</p>
      <ul v-else class="admin-audit-list">
        <li v-for="log in auditLogs" :key="log.id">
          <span class="admin-audit-actor">{{ log.actor_username }}</span>
          {{ log.detail }}
          <span class="admin-audit-time">{{ formatRelative(log.created_at) }}</span>
        </li>
      </ul>
    </article>

    <!-- 編輯 modal -->
    <div v-if="editModal.open" class="admin-modal-overlay" @click.self="closeEdit">
      <div class="admin-modal">
        <div class="admin-modal-header">
          <h3>編輯帳號：{{ editModal.username }}</h3>
          <button type="button" class="admin-modal-close" @click="closeEdit">✕</button>
        </div>

        <form class="admin-modal-form" @submit.prevent="submitEdit">
          <label>
            <span>顯示名稱</span>
            <input v-model="editModal.display_name" type="text" />
          </label>

          <label>
            <span>角色</span>
            <select v-model="editModal.role" :disabled="editModal.isSelf">
              <option value="user">一般使用者</option>
              <option value="admin">管理員</option>
            </select>
            <small v-if="editModal.isSelf" class="admin-modal-hint">不能調整自己的角色</small>
          </label>

          <label class="admin-modal-checkbox">
            <input v-model="editModal.is_active" type="checkbox" :disabled="editModal.isSelf" />
            <span>啟用此帳號</span>
            <small v-if="editModal.isSelf" class="admin-modal-hint">不能停用自己</small>
          </label>

          <label>
            <span>重設密碼（留空則不變）</span>
            <input v-model="editModal.new_password" type="password" autocomplete="new-password" placeholder="至少 6 個字元" />
          </label>

          <div class="admin-modal-footer">
            <button type="button" class="admin-modal-cancel" @click="closeEdit">取消</button>
            <button type="submit" class="admin-modal-save" :disabled="editModal.submitting">
              {{ editModal.submitting ? "儲存中…" : "儲存變更" }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>
