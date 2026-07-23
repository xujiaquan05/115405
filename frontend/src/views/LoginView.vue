<!-- frontend/src/views/LoginView.vue -->

<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { useAuth } from "../composables/useAuth";
import LogoMark from "../components/LogoMark.vue";

const router = useRouter();
const { state: authState, login, enterGuestMode } = useAuth();

const form = reactive({
  username: "",
  password: "",
  remember: true,
});

const showPassword = ref(false);

async function handleLogin() {
  if (authState.loading) return;

  if (!form.username.trim() || !form.password) {
    authState.errorMessage = "請輸入帳號與密碼。";
    return;
  }

  const success = await login(form.username.trim(), form.password);

  if (success) {
    router.push("/dashboard");
  }
}

function handleGuest() {
  enterGuestMode();
  router.push("/dashboard");
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">

      <!-- 左側品牌介紹面板 -->
      <aside class="login-brand">
        <div>
          <div class="login-brand-title">
            <LogoMark :size="40" />
            <div>
              <strong class="login-wordmark">MeBOD</strong>
              <h1>醫美時尚輿情分析系統</h1>
            </div>
          </div>
          <p class="login-brand-subtitle">Medical Beauty Opinion Dashboard</p>

          <ul class="login-feature-list">
            <li>
              <span class="login-feature-icon">◎</span>
              <div>
                <strong>即時輿情監測</strong>
                <p>追蹤 PTT 十大美容看板討論</p>
              </div>
            </li>
            <li>
              <span class="login-feature-icon">☺</span>
              <div>
                <strong>AI 情緒分析</strong>
                <p>Gemini 自動判讀正負評</p>
              </div>
            </li>
            <li>
              <span class="login-feature-icon">✦</span>
              <div>
                <strong>行銷洞察建議</strong>
                <p>AI 問答與趨勢報告</p>
              </div>
            </li>
          </ul>
        </div>

        <p class="login-brand-footer">115405 專題製作</p>
      </aside>

      <!-- 右側登入表單 -->
      <section class="login-form-panel">
        <h2>登入</h2>
        <p class="login-form-hint">使用帳號密碼登入系統</p>

        <p v-if="authState.errorMessage" class="login-error">
          {{ authState.errorMessage }}
        </p>

        <form @submit.prevent="handleLogin">
          <label class="login-label" for="login-username">帳號</label>
          <div class="login-input-wrap">
            <input
              id="login-username"
              v-model="form.username"
              type="text"
              autocomplete="username"
              placeholder="請輸入帳號"
            />
          </div>

          <label class="login-label" for="login-password">密碼</label>
          <div class="login-input-wrap">
            <input
              id="login-password"
              v-model="form.password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="請輸入密碼"
            />
            <button
              type="button"
              class="login-eye-button"
              :aria-label="showPassword ? '隱藏密碼' : '顯示密碼'"
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? "隱藏" : "顯示" }}
            </button>
          </div>

          <button class="login-submit-button" type="submit" :disabled="authState.loading">
            {{ authState.loading ? "登入中…" : "登入" }}
          </button>
        </form>

        <div class="login-divider">
          <span>或</span>
        </div>

        <button class="login-guest-button" type="button" @click="handleGuest">
          以訪客身分瀏覽 Dashboard
        </button>

        <p class="login-footnote">
          還沒有帳號？請聯絡系統管理員建立。
        </p>
      </section>

    </div>
  </div>
</template>
