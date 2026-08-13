<!-- frontend/src/views/ProfileView.vue -->

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useAuth } from "../composables/useAuth";
import api from "../services/api";

const { state: authState, updateUser } = useAuth();

const user = computed(() => authState.user || {});

const initial = computed(() => {
  const name = user.value.display_name || user.value.username || "?";
  return name.slice(0, 1).toUpperCase();
});

const roleLabel = computed(() => {
  return user.value.role === "admin" ? "系統管理員" : "一般使用者";
});

function formatDateTime(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hour12: false,
  }).format(new Date(value));
}

// ── 編輯顯示名稱 ──────────────────────────────────────────────
const nameEdit = reactive({
  editing: false,
  value: "",
  saving: false,
  message: "",
  messageType: "info",
});

function startEditName() {
  nameEdit.value = user.value.display_name || "";
  nameEdit.message = "";
  nameEdit.editing = true;
}

function cancelEditName() {
  nameEdit.editing = false;
  nameEdit.message = "";
}

async function saveName() {
  const name = nameEdit.value.trim();
  if (!name) {
    nameEdit.message = "顯示名稱不可空白。";
    nameEdit.messageType = "error";
    return;
  }
  if (name === user.value.display_name) {
    nameEdit.editing = false;
    return;
  }

  nameEdit.saving = true;
  try {
    const response = await api.patch("/api/auth/me", { display_name: name });
    updateUser(response.data.user);
    nameEdit.editing = false;
    nameEdit.message = "顯示名稱已更新。";
    nameEdit.messageType = "success";
  } catch (error) {
    console.error(error);
    nameEdit.message = error.response?.data?.detail || "更新失敗，請稍後再試。";
    nameEdit.messageType = "error";
  } finally {
    nameEdit.saving = false;
  }
}

// ── 修改密碼 ──────────────────────────────────────────────────
const form = reactive({
  oldPassword: "",
  newPassword: "",
  confirmPassword: "",
  loading: false,
  errorMessage: "",
  successMessage: "",
});

// 各欄位是否顯示明碼
const reveal = reactive({ old: false, new: false, confirm: false });

// 新密碼強度：依長度與字元多樣性給 弱 / 中 / 強。
const passwordStrength = computed(() => {
  const p = form.newPassword;
  if (!p) return { level: 0, label: "", cls: "" };

  let score = 0;
  if (p.length >= 6) score += 1;
  if (p.length >= 10) score += 1;
  if (/[A-Za-z]/.test(p) && /\d/.test(p)) score += 1;
  if (/[^A-Za-z0-9]/.test(p)) score += 1;

  if (score <= 1) return { level: 1, label: "弱", cls: "weak" };
  if (score === 2) return { level: 2, label: "中", cls: "medium" };
  return { level: 3, label: "強", cls: "strong" };
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
  if (form.newPassword === form.oldPassword) {
    form.errorMessage = "新密碼不可與舊密碼相同。";
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

// 進頁面時抓最新資料（含最後登入、建立時間），並同步到全域狀態。
onMounted(async () => {
  try {
    const response = await api.get("/api/auth/me");
    updateUser(response.data.user);
  } catch (error) {
    console.error(error);
  }
});
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
          <div class="profile-identity-text">
            <div v-if="!nameEdit.editing" class="profile-name-row">
              <strong>{{ user.display_name || user.username }}</strong>
              <button class="profile-edit-btn" type="button" aria-label="編輯顯示名稱" @click="startEditName">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z" />
                </svg>
              </button>
            </div>

            <div v-else class="profile-name-edit">
              <input
                v-model="nameEdit.value"
                type="text"
                maxlength="100"
                placeholder="顯示名稱"
                @keydown.enter="saveName"
              />
              <button class="profile-name-save" type="button" :disabled="nameEdit.saving" @click="saveName">
                {{ nameEdit.saving ? "儲存中…" : "儲存" }}
              </button>
              <button class="profile-name-cancel" type="button" @click="cancelEditName">取消</button>
            </div>

            <p>@{{ user.username }}</p>
          </div>
        </div>

        <p v-if="nameEdit.message" :class="['profile-message', nameEdit.messageType]">{{ nameEdit.message }}</p>

        <dl class="profile-detail-list">
          <div>
            <dt>角色</dt>
            <dd><span :class="['profile-role-badge', user.role === 'admin' ? 'is-admin' : '']">{{ roleLabel }}</span></dd>
          </div>
          <div>
            <dt>帳號 ID</dt>
            <dd>{{ user.id }}</dd>
          </div>
          <div>
            <dt>狀態</dt>
            <dd>
              <span :class="['profile-status-badge', user.is_active === false ? 'is-off' : 'is-on']">
                {{ user.is_active === false ? "已停用" : "啟用中" }}
              </span>
            </dd>
          </div>
          <div>
            <dt>最後登入</dt>
            <dd>{{ formatDateTime(user.last_login_at) }}</dd>
          </div>
          <div>
            <dt>建立時間</dt>
            <dd>{{ formatDateTime(user.created_at) }}</dd>
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
            <div class="profile-pw-field">
              <input v-model="form.oldPassword" :type="reveal.old ? 'text' : 'password'" autocomplete="current-password" />
              <button class="profile-pw-toggle" type="button" :aria-label="reveal.old ? '隱藏密碼' : '顯示密碼'" @click="reveal.old = !reveal.old">
                <svg v-if="reveal.old" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20C5 20 1 12 1 12a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19M1 1l22 22" /><path d="M9.5 9.5a3 3 0 0 0 4.24 4.24" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                </svg>
              </button>
            </div>
          </label>

          <label>
            <span>新密碼（至少 6 個字元）</span>
            <div class="profile-pw-field">
              <input v-model="form.newPassword" :type="reveal.new ? 'text' : 'password'" autocomplete="new-password" />
              <button class="profile-pw-toggle" type="button" :aria-label="reveal.new ? '隱藏密碼' : '顯示密碼'" @click="reveal.new = !reveal.new">
                <svg v-if="reveal.new" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20C5 20 1 12 1 12a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19M1 1l22 22" /><path d="M9.5 9.5a3 3 0 0 0 4.24 4.24" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                </svg>
              </button>
            </div>

            <div v-if="form.newPassword" class="profile-strength">
              <div class="profile-strength-track">
                <div :class="['profile-strength-bar', passwordStrength.cls]" :style="{ width: `${passwordStrength.level * 33.3}%` }"></div>
              </div>
              <span :class="['profile-strength-label', passwordStrength.cls]">強度：{{ passwordStrength.label }}</span>
            </div>
          </label>

          <label>
            <span>確認新密碼</span>
            <div class="profile-pw-field">
              <input v-model="form.confirmPassword" :type="reveal.confirm ? 'text' : 'password'" autocomplete="new-password" />
              <button class="profile-pw-toggle" type="button" :aria-label="reveal.confirm ? '隱藏密碼' : '顯示密碼'" @click="reveal.confirm = !reveal.confirm">
                <svg v-if="reveal.confirm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20C5 20 1 12 1 12a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19M1 1l22 22" /><path d="M9.5 9.5a3 3 0 0 0 4.24 4.24" />
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                </svg>
              </button>
            </div>
          </label>

          <button class="profile-submit" type="submit" :disabled="form.loading">
            {{ form.loading ? "更新中…" : "更新密碼" }}
          </button>
        </form>
      </article>
    </div>
  </section>
</template>
