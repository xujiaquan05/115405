<!-- frontend/src/views/AdminUsersView.vue -->

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useAuth } from "../composables/useAuth";
import api from "../services/api";

const { state: authState } = useAuth();
const currentUserId = computed(() => authState.user?.id);

const users = ref([]);
const loading = ref(false);
const errorMessage = ref("");
const successMessage = ref("");

const createForm = reactive({
  username: "",
  display_name: "",
  password: "",
  role: "user",
  submitting: false,
});

function flashSuccess(message) {
  successMessage.value = message;
  errorMessage.value = "";
}

function flashError(error, fallback) {
  errorMessage.value = error.response?.data?.detail || fallback;
  successMessage.value = "";
}

async function fetchUsers() {
  loading.value = true;
  errorMessage.value = "";

  try {
    const response = await api.get("/api/admin/users");
    users.value = response.data.data.users;
  } catch (error) {
    console.error(error);
    flashError(error, "載入使用者清單失敗。");
  } finally {
    loading.value = false;
  }
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
    await fetchUsers();
  } catch (error) {
    console.error(error);
    flashError(error, "建立帳號失敗。");
  } finally {
    createForm.submitting = false;
  }
}

async function patchUser(user, payload, successText) {
  try {
    await api.patch(`/api/admin/users/${user.id}`, payload);
    flashSuccess(successText);
    await fetchUsers();
  } catch (error) {
    console.error(error);
    flashError(error, "更新失敗。");
  }
}

function toggleActive(user) {
  patchUser(
    user,
    { is_active: !user.is_active },
    `已${user.is_active ? "停用" : "啟用"}帳號「${user.username}」。`
  );
}

function toggleRole(user) {
  const nextRole = user.role === "admin" ? "user" : "admin";
  patchUser(user, { role: nextRole }, `已將「${user.username}」設為 ${nextRole === "admin" ? "管理員" : "一般使用者"}。`);
}

async function resetPassword(user) {
  const newPassword = window.prompt(`為「${user.username}」設定新密碼（至少 6 個字元）：`);
  if (newPassword === null) return;

  if (newPassword.length < 6) {
    flashError({}, "新密碼至少需要 6 個字元。");
    return;
  }

  patchUser(user, { new_password: newPassword }, `已重設「${user.username}」的密碼。`);
}

async function deleteUser(user) {
  if (!window.confirm(`確定要刪除帳號「${user.username}」嗎？此動作無法復原。`)) return;

  try {
    await api.delete(`/api/admin/users/${user.id}`);
    flashSuccess(`已刪除帳號「${user.username}」。`);
    await fetchUsers();
  } catch (error) {
    console.error(error);
    flashError(error, "刪除失敗。");
  }
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("zh-TW");
}

onMounted(fetchUsers);
</script>

<template>
  <section class="admin-page">
    <div class="admin-page-header">
      <h2>帳號管理</h2>
      <p>建立、停用或調整系統使用者的權限。</p>
    </div>

    <p v-if="errorMessage" class="admin-message error">{{ errorMessage }}</p>
    <p v-if="successMessage" class="admin-message success">{{ successMessage }}</p>

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

    <article class="card admin-list-card">
      <div class="admin-list-header">
        <h3>使用者清單</h3>
        <button class="admin-ghost-button" type="button" @click="fetchUsers">⟳ 重新整理</button>
      </div>

      <p v-if="loading" class="admin-empty">載入中…</p>
      <p v-else-if="!users.length" class="admin-empty">目前沒有使用者。</p>

      <div v-else class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>帳號</th>
              <th>顯示名稱</th>
              <th>角色</th>
              <th>狀態</th>
              <th>建立日期</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>
                {{ user.username }}
                <span v-if="user.id === currentUserId" class="admin-self-tag">你</span>
              </td>
              <td>{{ user.display_name }}</td>
              <td>
                <span :class="['admin-role-badge', user.role === 'admin' ? 'is-admin' : '']">
                  {{ user.role === "admin" ? "管理員" : "一般使用者" }}
                </span>
              </td>
              <td>
                <span :class="['admin-status-dot', user.is_active ? 'is-active' : 'is-inactive']">
                  {{ user.is_active ? "啟用中" : "已停用" }}
                </span>
              </td>
              <td>{{ formatDate(user.created_at) }}</td>
              <td>
                <div class="admin-actions">
                  <button type="button" @click="toggleRole(user)" :disabled="user.id === currentUserId">
                    {{ user.role === "admin" ? "改一般" : "設管理員" }}
                  </button>
                  <button type="button" @click="toggleActive(user)" :disabled="user.id === currentUserId">
                    {{ user.is_active ? "停用" : "啟用" }}
                  </button>
                  <button type="button" @click="resetPassword(user)">重設密碼</button>
                  <button type="button" class="admin-danger" @click="deleteUser(user)" :disabled="user.id === currentUserId">
                    刪除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>
