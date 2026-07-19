<!-- frontend/src/views/ProfileView.vue -->

<script setup>
import { computed, reactive } from "vue";
import { useAuth } from "../composables/useAuth";
import api from "../services/api";

const { state: authState } = useAuth();

const user = computed(() => authState.user || {});

const initial = computed(() => {
  const name = user.value.display_name || user.value.username || "?";
  return name.slice(0, 1).toUpperCase();
});

const roleLabel = computed(() => {
  return user.value.role === "admin" ? "系統管理員" : "一般使用者";
});

const form = reactive({
  oldPassword: "",
  newPassword: "",
  confirmPassword: "",
  loading: false,
  errorMessage: "",
  successMessage: "",
});

async function handleChangePassword() {
  if (form.loading) return;

  form.errorMessage = "";
  form.successMessage = "";

  if (!form.oldPassword || !form.newPassword || !form.confirmPassword) {
    form.errorMessage = "請填寫所有欄位。";
    return;
  }

  if (form.newPassword.length < 6) {
    form.errorMessage = "新密碼至少需要 6 個字元。";
    return;
  }

  if (form.newPassword !== form.confirmPassword) {
    form.errorMessage = "兩次輸入的新密碼不一致。";
    return;
  }

  form.loading = true;

  try {
    const response = await api.post("/api/auth/change-password", {
      old_password: form.oldPassword,
      new_password: form.newPassword,
    });

    form.successMessage = response.data.message || "密碼已更新。";
    form.oldPassword = "";
    form.newPassword = "";
    form.confirmPassword = "";
  } catch (error) {
    console.error(error);
    form.errorMessage = error.response?.data?.detail || "密碼更新失敗，請稍後再試。";
  } finally {
    form.loading = false;
  }
}
</script>

<template>
  <section class="profile-page">
    <div class="profile-page-header">
      <h2>帳號資訊</h2>
      <p>檢視你的帳號資料並管理登入密碼。</p>
    </div>

    <div class="profile-grid">
      <article class="card profile-card">
        <div class="profile-identity">
          <div class="profile-avatar">{{ initial }}</div>
          <div>
            <strong>{{ user.display_name || user.username }}</strong>
            <p>@{{ user.username }}</p>
          </div>
        </div>

        <dl class="profile-detail-list">
          <div>
            <dt>角色</dt>
            <dd><span :class="['profile-role-badge', user.role === 'admin' ? 'is-admin' : '']">{{ roleLabel }}</span></dd>
          </div>
          <div>
            <dt>帳號 ID</dt>
            <dd>{{ user.id }}</dd>
          </div>
        </dl>
      </article>

      <article class="card profile-card">
        <h3>修改密碼</h3>

        <p v-if="form.errorMessage" class="profile-message error">{{ form.errorMessage }}</p>
        <p v-if="form.successMessage" class="profile-message success">{{ form.successMessage }}</p>

        <form class="profile-form" @submit.prevent="handleChangePassword">
          <label>
            <span>舊密碼</span>
            <input v-model="form.oldPassword" type="password" autocomplete="current-password" />
          </label>

          <label>
            <span>新密碼（至少 6 個字元）</span>
            <input v-model="form.newPassword" type="password" autocomplete="new-password" />
          </label>

          <label>
            <span>確認新密碼</span>
            <input v-model="form.confirmPassword" type="password" autocomplete="new-password" />
          </label>

          <button type="submit" :disabled="form.loading">
            {{ form.loading ? "更新中…" : "更新密碼" }}
          </button>
        </form>
      </article>
    </div>
  </section>
</template>
