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
});

const messageList = ref(null);

const activeConversation = computed(() => {
  return state.conversations.find((conversation) => conversation.id === state.activeConversationId) || null;
});

const messages = computed(() => activeConversation.value?.messages || []);

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
    answer: "我會根據目前 Dashboard 的分析資料回答，包括關鍵字、文章數、情緒分布、熱門文章與 LLM 洞察。你可以直接問這次分析代表什麼、風險在哪裡、或下一步行銷該怎麼做。",
    key_points: [],
    marketing_action: "",
    confidence: "",
    sources: [],
  };
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

async function askQuestion(questionText = state.question) {
  const question = questionText.trim();

  if (!question || state.loading) return;

  if (!activeConversation.value) {
    createConversation();
  }

  state.question = "";
  state.errorMessage = "";
  state.loading = true;

  activeConversation.value.messages.push({
    id: Date.now(),
    role: "user",
    text: question,
  });

  updateConversationAfterQuestion(question);
  saveConversations();
  await scrollToBottom();

  try {
    await ensureDashboardContext();

    const response = await api.post("/api/qa/ask", {
      question,
      dashboard_context: dashboardContext.value,
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
    });

    activeConversation.value.updatedAt = new Date().toISOString();
    saveConversations();
  } catch (error) {
    console.error(error);
    state.errorMessage = error.response?.status === 429
      ? "提問太頻繁，請稍等一分鐘再試。"
      : "AI Q&A failed. Please check backend, database, or Gemini API settings.";
  } finally {
    state.loading = false;
    await scrollToBottom();
  }
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
    <div class="qa-chat-area">
      <div class="qa-header">
        <h2>AI 問答</h2>
        <p>
          目前依據 Dashboard「{{ dashboardState.keyword }}」的分析資料回答，包含指標、情緒、熱門文章與洞察。
        </p>
      </div>

      <p v-if="state.errorMessage" class="error-message">
        {{ state.errorMessage }}
      </p>

      <div ref="messageList" class="chat-panel">
        <article
          v-for="message in messages"
          :key="message.id"
          class="chat-message"
          :class="message.role"
        >
          <div v-if="message.role === 'assistant'" class="message-avatar">
            AI
          </div>

          <div v-if="message.role === 'user'" class="user-bubble">
            {{ message.text }}
          </div>

          <div v-else class="assistant-bubble">
            <p class="qa-answer">{{ message.answer }}</p>

            <div v-if="message.key_points?.length" class="qa-block">
              <h3>Key Points</h3>
              <ul>
                <li v-for="point in message.key_points" :key="point">
                  {{ point }}
                </li>
              </ul>
            </div>

            <div v-if="message.marketing_action" class="qa-action">
              {{ message.marketing_action }}
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
                    {{ source.board }} · {{ source.author }} · 推 {{ source.push_count }}
                  </span>
                  <small>{{ source.published_at }}</small>
                </a>
              </div>
            </div>

            <div v-if="message.confidence" class="confidence-row">
              Confidence: {{ message.confidence }}
            </div>
          </div>
        </article>

        <article v-if="state.loading" class="chat-message assistant">
          <div class="message-avatar">AI</div>
          <div class="assistant-bubble loading-bubble">
            Analyzing Dashboard context...
          </div>
        </article>
      </div>

      <div class="qa-composer">
        <div class="quick-question-row">
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
          <input
            v-model="state.question"
            type="text"
            placeholder="問目前 Dashboard 的分析結果..."
          />
          <button class="qa-send-button" type="submit" :disabled="state.loading">
            ↑
          </button>
        </form>
      </div>
    </div>
  </section>
</template>
