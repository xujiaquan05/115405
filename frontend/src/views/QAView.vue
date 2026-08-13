<!-- frontend/src/views/QAView.vue -->

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";

import api from "../services/api.js";
import {
  DASHBOARD_ANALYSIS_CONTEXT_KEY,
  TARGET_BOARDS,
  useDashboard,
} from "../composables/useDashboard.js";

const STORAGE_KEY = "qa-conversations";
const DEFAULT_CONVERSATION_TITLE = "新的對話";

const quickQuestions = [
  "根據目前 Dashboard，最大的負面風險是什麼？",
  "目前最適合主打哪一個行銷角度？",
  "熱門文章裡消費者最在意什麼？",
  "這次分析中有哪些內容機會？",
];

const {
  state: dashboardState,
  overview,
  sentiment,
  hotArticles,
  keywords,
  fetchDashboard,
  fetchInsight,
} = useDashboard();

const state = reactive({
  question: "",
  loading: false,
  errorMessage: "",
  conversations: [],
  activeConversationId: null,
  searchText: "",
  openMenuId: null,
  editingConversationId: null,
  editingTitle: "",
  lastQuestion: "",
});

const PLATFORM_LABELS = { ptt: "PTT", dcard: "Dcard" };
function platformLabel(name) {
  return PLATFORM_LABELS[name] || name;
}

const messageList = ref(null);
const composerRef = ref(null);
const copiedMessageId = ref(null);

// 行動版：側邊「對話紀錄」抽屜開關（桌機一律顯示）。
const showSidebar = ref(false);
function toggleSidebar() {
  showSidebar.value = !showSidebar.value;
}
function startNewChat() {
  createConversation();
  showSidebar.value = false;
}

// 信心程度：英文轉繁中標籤。
function confidenceLabel(conf) {
  return { high: "高", medium: "中", low: "低" }[conf] || conf;
}

// 來源文章的情緒標籤（AI 評分結果），沒有評分就回傳 null（不顯示）。
function sentimentInfo(sentiment) {
  const map = {
    positive: { label: "正面", cls: "is-positive" },
    neutral: { label: "中性", cls: "is-neutral" },
    negative: { label: "負面", cls: "is-negative" },
  };
  return map[sentiment] || null;
}

// 複製整段 AI 回答（含重點與行銷建議）到剪貼簿。
async function copyAnswer(message) {
  const parts = [message.answer];

  if (message.key_points?.length) {
    parts.push("\n重點整理：");
    message.key_points.forEach((point, index) => parts.push(`${index + 1}. ${point}`));
  }

  if (message.marketing_action) {
    parts.push(`\n行銷建議：${message.marketing_action}`);
  }

  try {
    await navigator.clipboard.writeText(parts.join("\n"));
    copiedMessageId.value = message.id;
    setTimeout(() => {
      if (copiedMessageId.value === message.id) copiedMessageId.value = null;
    }, 1500);
  } catch (error) {
    console.error(error);
  }
}

// Enter 送出、Shift+Enter 換行；輸入法組字中的 Enter 不送出。
function handleComposerKeydown(event) {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    askQuestion();
  }
}

// 輸入框隨內容自動長高（上限 120px）。
function autoGrowComposer() {
  const el = composerRef.value;
  if (!el) return;
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
}

function resetComposerHeight() {
  if (composerRef.value) composerRef.value.style.height = "auto";
}

const activeConversation = computed(() => {
  return state.conversations.find((conversation) => conversation.id === state.activeConversationId) || null;
});

const messages = computed(() => activeConversation.value?.messages || []);

// 只有「還沒問過任何問題」時才顯示快捷提問，開始對話後就收起，
// 把空間留給訊息內容。
const hasUserMessage = computed(() => messages.value.some((message) => message.role === "user"));

const sortedConversations = computed(() => {
  return [...state.conversations].sort((a, b) => {
    const pinnedDiff = Number(Boolean(b.pinned)) - Number(Boolean(a.pinned));

    if (pinnedDiff !== 0) return pinnedDiff;

    return new Date(b.updatedAt || 0) - new Date(a.updatedAt || 0);
  });
});

const filteredConversations = computed(() => {
  const keyword = state.searchText.trim().toLowerCase();
  const conversations = sortedConversations.value;

  if (!keyword) return conversations;

  return conversations.filter((conversation) => {
    return `${conversation.title} ${conversation.keyword}`.toLowerCase().includes(keyword);
  });
});

const dashboardContext = computed(() => ({
  keyword: dashboardState.keyword,
  days: dashboardState.days,
  overview: overview.value,
  sentiment: sentiment.value,
  keywords: keywords.value,
  hot_articles: hotArticles.value,
  insight: dashboardState.insightData,
  generated_at: new Date().toISOString(),
}));

function createWelcomeMessage() {
  return {
    id: Date.now(),
    role: "assistant",
    welcome: true,
    answer: "我會根據目前 Dashboard 的分析資料回答，包括關鍵字、文章數、情緒分布、熱門文章與 LLM 洞察。你可以直接問這次分析代表什麼、風險在哪裡、或下一步行銷該怎麼做。",
    key_points: [],
    marketing_action: "",
    confidence: "",
    sources: [],
  };
}

// 把對話訊息整理成傳給後端的 history（略過歡迎詞與空內容，只留最近 6 則）。
function toHistory(messages) {
  return (messages || [])
    .filter((message) => !message.welcome)
    .map((message) => ({
      role: message.role === "user" ? "user" : "assistant",
      content: message.role === "user" ? message.text || "" : message.answer || "",
    }))
    .filter((item) => item.content)
    .slice(-6);
}

function readDashboardAnalysisContext() {
  try {
    return JSON.parse(localStorage.getItem(DASHBOARD_ANALYSIS_CONTEXT_KEY) || "null");
  } catch {
    return null;
  }
}

function applyDashboardContextToState(context) {
  if (!context) return;

  if (context.keyword) {
    dashboardState.keyword = context.keyword;
  }

  if (context.days) {
    dashboardState.days = context.days;
  }

  if (Array.isArray(context.boards)) {
    const allBoards = TARGET_BOARDS.map((board) => board.name);
    const usesAllBoards =
      context.boards.length === allBoards.length &&
      allBoards.every((board) => context.boards.includes(board));

    dashboardState.selectedBoards = usesAllBoards ? [] : context.boards;
  }
}

function createConversation(title = DEFAULT_CONVERSATION_TITLE, dashboardContextId = "") {
  const conversation = {
    id: Date.now() + Math.random(),
    title,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    keyword: dashboardState.keyword,
    dashboardContextId,
    messages: [createWelcomeMessage()],
  };

  state.conversations.unshift(conversation);
  state.activeConversationId = conversation.id;
  saveConversations();
}

function ensureConversationForDashboardContext(context = readDashboardAnalysisContext()) {
  if (!context?.id) return;

  applyDashboardContextToState(context);

  const existingConversation = state.conversations.find((conversation) => {
    return conversation.dashboardContextId === context.id;
  });

  if (existingConversation) {
    state.activeConversationId = existingConversation.id;
    nextTick(scrollToBottom);
    return;
  }

  createConversation(DEFAULT_CONVERSATION_TITLE, context.id);
}

function saveConversations() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.conversations.slice(0, 30)));
}

function loadConversations() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    state.conversations = Array.isArray(saved) ? saved : [];
  } catch {
    state.conversations = [];
  }

  if (!state.conversations.length) {
    const context = readDashboardAnalysisContext();
    applyDashboardContextToState(context);
    createConversation(DEFAULT_CONVERSATION_TITLE, context?.id || "");
    return;
  }

  state.activeConversationId = state.conversations[0].id;
}

function selectConversation(conversationId) {
  state.activeConversationId = conversationId;
  state.openMenuId = null;
  state.editingConversationId = null;
  showSidebar.value = false;  // 行動版選完自動收起抽屜
  nextTick(scrollToBottom);
}

function deleteConversation(conversationId) {
  state.conversations = state.conversations.filter((conversation) => conversation.id !== conversationId);

  if (!state.conversations.length) {
    createConversation();
    return;
  }

  if (state.activeConversationId === conversationId) {
    state.activeConversationId = state.conversations[0].id;
  }

  saveConversations();
}

function renameConversation(conversationId, title) {
  const conversation = state.conversations.find((item) => item.id === conversationId);

  if (!conversation) return;

  conversation.title = title.trim() || DEFAULT_CONVERSATION_TITLE;
  conversation.manuallyRenamed = true;
  conversation.updatedAt = new Date().toISOString();
  saveConversations();
}

async function startRenameConversation(conversationId) {
  const conversation = state.conversations.find((item) => item.id === conversationId);

  if (!conversation) return;

  state.openMenuId = null;
  state.editingConversationId = conversationId;
  state.editingTitle = conversation.title;
  await nextTick();
}

function finishRenameConversation(conversationId) {
  if (state.editingConversationId !== conversationId) return;

  renameConversation(conversationId, state.editingTitle);
  state.editingConversationId = null;
  state.editingTitle = "";
}

function toggleConversationMenu(conversationId) {
  state.openMenuId = state.openMenuId === conversationId ? null : conversationId;
}

function togglePinnedConversation(conversationId) {
  const conversation = state.conversations.find((item) => item.id === conversationId);

  if (!conversation) return;

  conversation.pinned = !conversation.pinned;
  conversation.updatedAt = new Date().toISOString();
  state.openMenuId = null;
  saveConversations();
}

function toggleMessageSources(message) {
  message.sourcesExpanded = !message.sourcesExpanded;
  saveConversations();
  nextTick(scrollToBottom);
}

function formatConversationTime(value) {
  if (!value) return "";

  return new Intl.DateTimeFormat("zh-TW", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

async function scrollToBottom() {
  await nextTick();

  if (messageList.value) {
    messageList.value.scrollTop = messageList.value.scrollHeight;
  }
}

function updateConversationAfterQuestion(question) {
  const conversation = activeConversation.value;

  if (!conversation) return;

  const userMessageCount = conversation.messages.filter((message) => message.role === "user").length;

  if (!conversation.manuallyRenamed && userMessageCount === 1) {
    conversation.title = question.slice(0, 28);
  }

  conversation.keyword = dashboardState.keyword;
  conversation.updatedAt = new Date().toISOString();
}

async function ensureDashboardContext() {
  if (!dashboardState.dashboardData) {
    await fetchDashboard();
  }

  if (!dashboardState.insightData) {
    fetchInsight();
  }
}

// 實際呼叫後端並把回答加進對話。question 為要回答的問題，
// history 為該問題之前的對話脈絡，noCache=true 時強制重新生成。
async function runAnswer(question, history, { noCache = false } = {}) {
  if (!activeConversation.value) return;

  state.loading = true;
  await scrollToBottom();

  try {
    await ensureDashboardContext();

    const response = await api.post("/api/qa/ask", {
      question,
      dashboard_context: dashboardContext.value,
      history,
      no_cache: noCache,
    });
    const result = response.data.result;

    activeConversation.value.messages.push({
      id: Date.now() + 1,
      role: "assistant",
      answer: result.answer,
      key_points: result.key_points || [],
      marketing_action: result.marketing_action,
      confidence: result.confidence,
      sources: result.sources || [],
      sourcesExpanded: false,
      intent: result.intent,
      question,  // 記住對應問題，供「重新生成」使用
    });

    activeConversation.value.updatedAt = new Date().toISOString();
    saveConversations();
  } catch (error) {
    console.error(error);
    state.errorMessage = error.response?.status === 429
      ? "提問太頻繁，請稍等一分鐘再試。"
      : "AI 問答發生錯誤，請確認後端、資料庫或 Gemini API 設定。";
  } finally {
    state.loading = false;
    await scrollToBottom();
  }
}

async function askQuestion(questionText = state.question) {
  const question = questionText.trim();

  if (!question || state.loading) return;

  if (!activeConversation.value) {
    createConversation();
  }

  state.question = "";
  resetComposerHeight();
  state.errorMessage = "";
  state.lastQuestion = question;

  // history = 這則新問題「之前」的對話脈絡（在推入使用者訊息前先取）。
  const history = toHistory(activeConversation.value.messages);

  activeConversation.value.messages.push({
    id: Date.now(),
    role: "user",
    text: question,
  });

  updateConversationAfterQuestion(question);
  saveConversations();

  await runAnswer(question, history);
}

// 重新生成某則 AI 回答：用它對應的問題重新詢問（略過快取），並取代原回答。
async function regenerateMessage(message) {
  if (state.loading) return;

  const messages = activeConversation.value?.messages || [];
  const index = messages.indexOf(message);
  if (index === -1) return;

  // 對應的使用者問題通常就在這則回答的前一則。
  const userIndex = index - 1;
  const question = message.question
    || (messages[userIndex]?.role === "user" ? messages[userIndex].text : "");
  if (!question) return;

  const history = toHistory(messages.slice(0, userIndex));
  messages.splice(index, 1);  // 移除舊回答，稍後補上新回答
  state.errorMessage = "";
  saveConversations();

  await runAnswer(question, history, { noCache: true });
}

// 發生錯誤後重試最後一個問題（使用者訊息已在列表中，不重複推入）。
async function retryLast() {
  if (state.loading || !state.lastQuestion) return;

  const messages = activeConversation.value?.messages || [];
  const lastUserIndex = messages.map((m) => m.role).lastIndexOf("user");
  const history = toHistory(messages.slice(0, lastUserIndex));

  state.errorMessage = "";
  await runAnswer(state.lastQuestion, history, { noCache: true });
}

onMounted(() => {
  loadConversations();
  ensureConversationForDashboardContext();
  ensureDashboardContext();
  window.addEventListener("dashboard-analysis-context-created", handleDashboardContextCreated);
});

onBeforeUnmount(() => {
  window.removeEventListener("dashboard-analysis-context-created", handleDashboardContextCreated);
});

watch(
  () => dashboardState.analysisContextId,
  () => {
    ensureConversationForDashboardContext();
  }
);

function handleDashboardContextCreated(event) {
  ensureConversationForDashboardContext(event.detail);
}
</script>

<template>
  <section class="qa-page">
    <!-- 行動版抽屜遮罩 -->
    <div v-if="showSidebar" class="qa-sidebar-backdrop" @click="showSidebar = false"></div>

    <!-- 側邊：對話紀錄 -->
    <aside class="qa-sidebar" :class="{ open: showSidebar }">
      <button class="qa-new-chat" type="button" @click="startNewChat">
        <svg class="qa-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        新對話
      </button>

      <div class="qa-search">
        <svg class="qa-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input v-model="state.searchText" type="text" placeholder="搜尋對話…" />
      </div>

      <div class="qa-conversation-list">
        <p v-if="!filteredConversations.length" class="qa-conv-empty">沒有符合的對話。</p>

        <div
          v-for="conversation in filteredConversations"
          :key="conversation.id"
          class="qa-conversation-item"
          :class="{ active: conversation.id === state.activeConversationId }"
          @click="selectConversation(conversation.id)"
        >
          <input
            v-if="state.editingConversationId === conversation.id"
            v-model="state.editingTitle"
            class="qa-conv-rename"
            type="text"
            @click.stop
            @keydown.enter="finishRenameConversation(conversation.id)"
            @blur="finishRenameConversation(conversation.id)"
          />

          <template v-else>
            <div class="qa-conv-body">
              <div class="qa-conv-title-row">
                <svg v-if="conversation.pinned" class="qa-pin-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M14 4v5l3 3v2h-5v5l-1 1-1-1v-5H4v-2l3-3V4z" />
                </svg>
                <span class="qa-conv-title">{{ conversation.title }}</span>
              </div>
              <span class="qa-conv-time">{{ formatConversationTime(conversation.updatedAt) }}</span>
            </div>

            <button
              class="qa-conv-menu-btn"
              type="button"
              aria-label="更多操作"
              @click.stop="toggleConversationMenu(conversation.id)"
            >
              <svg class="qa-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <circle cx="5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="19" cy="12" r="1.6" />
              </svg>
            </button>

            <div v-if="state.openMenuId === conversation.id" class="qa-conv-menu" @click.stop>
              <button type="button" @click="togglePinnedConversation(conversation.id)">
                {{ conversation.pinned ? "取消置頂" : "置頂" }}
              </button>
              <button type="button" @click="startRenameConversation(conversation.id)">重新命名</button>
              <button type="button" class="danger" @click="deleteConversation(conversation.id)">刪除</button>
            </div>
          </template>
        </div>
      </div>
    </aside>

    <!-- 主聊天區 -->
    <div class="qa-chat-area">
      <div class="qa-header">
        <button class="qa-sidebar-toggle" type="button" aria-label="對話紀錄" @click="toggleSidebar">
          <svg class="qa-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <div class="qa-header-text">
          <h2>AI 問答</h2>
          <p>
            目前依據 Dashboard「{{ dashboardState.keyword }}」的分析資料回答，包含指標、情緒、熱門文章與洞察。
          </p>
        </div>
      </div>

      <p v-if="state.errorMessage" class="error-message">
        {{ state.errorMessage }}
        <button
          v-if="state.lastQuestion && !state.loading"
          class="qa-retry-button"
          type="button"
          @click="retryLast"
        >
          重試
        </button>
      </p>

      <div ref="messageList" class="chat-panel">
        <article
          v-for="message in messages"
          :key="message.id"
          class="chat-message"
          :class="message.role"
        >
          <div v-if="message.role === 'assistant'" class="message-avatar" aria-hidden="true">
            AI
          </div>

          <div v-if="message.role === 'user'" class="user-bubble">
            {{ message.text }}
          </div>

          <div v-else class="assistant-bubble">
            <div class="assistant-bubble-top">
              <p class="qa-answer">{{ message.answer }}</p>
              <div v-if="message.answer" class="qa-answer-actions">
                <button
                  v-if="!message.welcome"
                  class="qa-icon-btn"
                  type="button"
                  aria-label="重新生成"
                  title="重新生成"
                  :disabled="state.loading"
                  @click="regenerateMessage(message)"
                >
                  <svg class="qa-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M21 12a9 9 0 1 1-3-6.7" /><polyline points="21 3 21 9 15 9" />
                  </svg>
                </button>
                <button
                  class="qa-icon-btn"
                  type="button"
                  :class="{ 'is-copied': copiedMessageId === message.id }"
                  :aria-label="copiedMessageId === message.id ? '已複製' : '複製'"
                  :title="copiedMessageId === message.id ? '已複製' : '複製'"
                  @click="copyAnswer(message)"
                >
                  <svg v-if="copiedMessageId === message.id" class="qa-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                  <svg v-else class="qa-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                </button>
              </div>
            </div>

            <div v-if="message.key_points?.length" class="qa-block">
              <h3>重點整理</h3>
              <ul>
                <li v-for="point in message.key_points" :key="point">
                  {{ point }}
                </li>
              </ul>
            </div>

            <div v-if="message.marketing_action" class="qa-action">
              <span class="qa-action-label">行銷建議</span>
              <span>{{ message.marketing_action }}</span>
            </div>

            <div v-if="message.sources?.length" class="qa-block source-toggle-block">
              <button
                class="source-toggle-button"
                type="button"
                :aria-expanded="Boolean(message.sourcesExpanded)"
                @click="toggleMessageSources(message)"
              >
                <span>{{ message.sourcesExpanded ? "收起資料來源" : "顯示資料來源" }}</span>
                <small>{{ message.sources.length }} 筆引用</small>
              </button>

              <div v-if="message.sourcesExpanded" class="source-list">
                <a
                  v-for="source in message.sources"
                  :key="source.id || source.title"
                  class="source-card"
                  :href="source.url"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <strong>{{ source.title }}</strong>
                  <span>
                    <em v-if="source.platform" class="source-platform">{{ platformLabel(source.platform) }}</em>
                    {{ source.board }} · {{ source.author }} · 推 {{ source.push_count }}
                    <em
                      v-if="sentimentInfo(source.sentiment)"
                      :class="['source-sentiment', sentimentInfo(source.sentiment).cls]"
                    >{{ sentimentInfo(source.sentiment).label }}</em>
                  </span>
                  <small>{{ source.published_at }}</small>
                </a>
              </div>
            </div>

            <div v-if="message.confidence" class="confidence-row">
              信心程度
              <span :class="['confidence-badge', `is-${message.confidence}`]">
                {{ confidenceLabel(message.confidence) }}
              </span>
            </div>
          </div>
        </article>

        <article v-if="state.loading" class="chat-message assistant">
          <div class="message-avatar" aria-hidden="true">AI</div>
          <div class="assistant-bubble loading-bubble">
            <span class="typing-dots" aria-hidden="true"><i></i><i></i><i></i></span>
            正在分析 Dashboard 資料…
          </div>
        </article>
      </div>

      <div class="qa-composer">
        <div v-if="!hasUserMessage" class="quick-question-row">
          <button
            v-for="question in quickQuestions"
            :key="question"
            class="quick-question"
            type="button"
            @click="askQuestion(question)"
          >
            {{ question }}
          </button>
        </div>

        <form class="qa-input-row" @submit.prevent="askQuestion()">
          <textarea
            ref="composerRef"
            v-model="state.question"
            rows="1"
            placeholder="問目前 Dashboard 的分析結果…（Enter 送出，Shift+Enter 換行）"
            @keydown="handleComposerKeydown"
            @input="autoGrowComposer"
          ></textarea>
          <button
            class="qa-send-button"
            type="submit"
            :disabled="state.loading || !state.question.trim()"
            aria-label="送出問題"
          >
            ↑
          </button>
        </form>
      </div>
    </div>
  </section>
</template>
