<!-- frontend/src/views/QAView.vue -->

<script setup>
import { nextTick, reactive, ref } from "vue";
import api from "../services/api.js";

const quickQuestions = [
  "最近玻尿酸有哪些負評？",
  "消費者最在意醫美診所的什麼問題？",
  "肉毒討論中有哪些行銷機會？",
  "雷射保養最近的討論趨勢是什麼？",
];

const state = reactive({
  question: "",
  loading: false,
  errorMessage: "",
  messages: [
    {
      id: 1,
      role: "assistant",
      answer: "可以直接問我醫美輿情問題，我會根據資料庫文章回答並附上來源。",
      key_points: [],
      marketing_action: "",
      confidence: "",
      sources: [],
    },
  ],
});

const messageList = ref(null);

async function scrollToBottom() {
  await nextTick();

  if (messageList.value) {
    messageList.value.scrollTop = messageList.value.scrollHeight;
  }
}

async function askQuestion(questionText = state.question) {
  const question = questionText.trim();

  if (!question || state.loading) return;

  state.question = "";
  state.errorMessage = "";
  state.loading = true;

  state.messages.push({
    id: Date.now(),
    role: "user",
    text: question,
  });

  await scrollToBottom();

  try {
    const response = await api.post("/api/qa/ask", { question });
    const result = response.data.result;

    state.messages.push({
      id: Date.now() + 1,
      role: "assistant",
      answer: result.answer,
      key_points: result.key_points || [],
      marketing_action: result.marketing_action,
      confidence: result.confidence,
      sources: result.sources || [],
      intent: result.intent,
    });
  } catch (error) {
    console.error(error);
    state.errorMessage = "AI Q&A failed. Please check backend, database, or Gemini API settings.";
  } finally {
    state.loading = false;
    await scrollToBottom();
  }
}
</script>

<template>
  <section class="qa-page">
    <div class="qa-header">
      <div>
        <h2 class="section-title">AI Q&A</h2>
        <p class="section-desc">
          Ask natural-language questions and verify every answer with article sources.
        </p>
      </div>
    </div>

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

    <p v-if="state.errorMessage" class="error-message">
      {{ state.errorMessage }}
    </p>

    <div ref="messageList" class="chat-panel">
      <article
        v-for="message in state.messages"
        :key="message.id"
        class="chat-message"
        :class="message.role"
      >
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

          <div v-if="message.sources?.length" class="qa-block">
            <h3>Sources</h3>
            <div class="source-list">
              <a
                v-for="source in message.sources"
                :key="source.id"
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

      <div v-if="state.loading" class="assistant-bubble loading-bubble">
        Analyzing articles...
      </div>
    </div>

    <form class="qa-input-row" @submit.prevent="askQuestion()">
      <input
        v-model="state.question"
        type="text"
        placeholder="例如：最近玻尿酸有哪些負評？"
      />
      <button class="primary-button" type="submit" :disabled="state.loading">
        Ask
      </button>
    </form>
  </section>
</template>
