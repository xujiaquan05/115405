<!-- frontend/src/views/ProfileView.vue -->

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useAuth } from "../composables/useAuth";
import { passwordStrength } from "../utils/password";
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

// ── 頭像自訂（顏色 + emoji） ──────────────────────────────────
const AVATAR_COLORS = ["#4f46e5", "#7c3aed", "#0f6e56", "#0369a1", "#be185d", "#b45309", "#dc2626", "#334155"];
const AVATAR_EMOJIS = ["", "😀", "🦊", "🐱", "🌸", "💄", "✨", "🌟", "💼", "🩺", "📊", "🔥"];

const avatarEdit = reactive({ open: false, color: "", emoji: "", saving: false });

// 有 emoji 就顯示 emoji，否則顯示名稱首字。
const avatarContent = computed(() => user.value.avatar_emoji || initial.value);
const avatarStyle = computed(() => {
  const color = user.value.avatar_color;
  return color ? { backgroundColor: color, color: "#ffffff" } : {};
});

function openAvatarEdit() {
  avatarEdit.color = user.value.avatar_color || AVATAR_COLORS[0];
  avatarEdit.emoji = user.value.avatar_emoji || "";
  avatarEdit.open = true;
}

function cancelAvatarEdit() {
  avatarEdit.open = false;
}

async function saveAvatar() {
  if (avatarEdit.saving) return;
  avatarEdit.saving = true;
  try {
    const response = await api.patch("/api/auth/me", {
      avatar_color: avatarEdit.color,
      avatar_emoji: avatarEdit.emoji,
    });
    updateUser(response.data.user);
    avatarEdit.open = false;
  } catch (error) {
    console.error(error);
  } finally {
    avatarEdit.saving = false;
  }
}

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

// 新密碼強度：弱 / 中 / 強（邏輯抽到 utils/password.js 方便單元測試）。
const strength = computed(() => passwordStrength(form.newPassword));

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

    <!-- 個人檔案 Hero：banner + 大頭像 + 名稱與標籤 -->
    <article class="profile-hero">
      <div class="profile-hero-banner"></div>
      <div class="profile-hero-main">
        <div class="profile-avatar-wrap">
          <div class="profile-avatar profile-avatar-lg" :style="avatarStyle">{{ avatarContent }}</div>
          <button class="profile-avatar-edit" type="button" aria-label="編輯頭像" @click="openAvatarEdit">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" />
            </svg>
          </button>
        </div>

        <div class="profile-hero-text">
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

          <p class="profile-username">@{{ user.username }}</p>

          <div class="profile-hero-badges">
            <span :class="['profile-role-badge', user.role === 'admin' ? 'is-admin' : '']">{{ roleLabel }}</span>
            <span :class="['profile-status-badge', user.is_active === false ? 'is-off' : 'is-on']">
              {{ user.is_active === false ? "已停用" : "啟用中" }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="avatarEdit.open" class="profile-avatar-picker">
        <div class="pap-group">
          <span class="pap-label">底色</span>
          <div class="pap-swatches">
            <button
              v-for="c in AVATAR_COLORS"
              :key="c"
              type="button"
              class="pap-color"
              :class="{ sel: avatarEdit.color === c }"
              :style="{ backgroundColor: c }"
              :aria-label="`底色 ${c}`"
              @click="avatarEdit.color = c"
            ></button>
          </div>
        </div>

        <div class="pap-group">
          <span class="pap-label">圖示</span>
          <div class="pap-swatches">
            <button
              v-for="e in AVATAR_EMOJIS"
              :key="e || 'initial'"
              type="button"
              class="pap-emoji"
              :class="{ sel: avatarEdit.emoji === e }"
              @click="avatarEdit.emoji = e"
            >{{ e || "字" }}</button>
          </div>
        </div>

        <div class="pap-actions">
          <button class="profile-name-save" type="button" :disabled="avatarEdit.saving" @click="saveAvatar">
            {{ avatarEdit.saving ? "儲存中…" : "儲存頭像" }}
          </button>
          <button class="profile-name-cancel" type="button" @click="cancelAvatarEdit">取消</button>
        </div>
      </div>

      <p v-if="nameEdit.message" :class="['profile-message', nameEdit.messageType]">{{ nameEdit.message }}</p>
    </article>

    <!-- 帳號資料：資訊磚 -->
    <div class="profile-tiles">
      <div class="profile-tile">
        <span>角色</span>
        <strong>{{ roleLabel }}</strong>
      </div>
      <div class="profile-tile">
        <span>帳號 ID</span>
        <strong>{{ user.id }}</strong>
      </div>
      <div class="profile-tile">
        <span>狀態</span>
        <strong>{{ user.is_active === false ? "已停用" : "啟用中" }}</strong>
      </div>
      <div class="profile-tile">
        <span>最後登入</span>
        <strong>{{ formatDateTime(user.last_login_at) }}</strong>
      </div>
      <div class="profile-tile">
        <span>建立時間</span>
        <strong>{{ formatDateTime(user.created_at) }}</strong>
      </div>
    </div>

    <!-- 安全性：修改密碼 -->
    <article class="card profile-security">
      <div class="profile-section-head">
        <h3>修改密碼</h3>
        <p>定期更換密碼，並避免與其他網站共用，以保護帳號安全。</p>
      </div>

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
                <div :class="['profile-strength-bar', strength.cls]" :style="{ width: `${strength.level * 33.3}%` }"></div>
              </div>
              <span :class="['profile-strength-label', strength.cls]">強度：{{ strength.label }}</span>
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
  </section>
</template>
