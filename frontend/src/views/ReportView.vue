<!-- frontend/src/views/ReportView.vue -->

<script setup>
import { computed, onMounted, reactive } from "vue";
import { useRoute, useRouter } from "vue-router";
import api from "../services/api.js";
import LogoMark from "../components/LogoMark.vue";

const route = useRoute();
const router = useRouter();

const state = reactive({
  loading: true,
  errorMessage: "",
  dashboard: null,
  insight: null,
});

const keyword = computed(() => route.query.keyword || "醫美");
const days = computed(() => Number(route.query.days || 30));
const generatedAt = new Intl.DateTimeFormat("zh-TW", {
  year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false,
}).format(new Date());

const overview = computed(() => state.dashboard?.overview || {});
const sentiment = computed(() => state.dashboard?.sentiment || {});
const hotArticles = computed(() => (state.dashboard?.hot_articles || []).slice(0, 5));
const keywords = computed(() => (state.dashboard?.keywords || []).slice(0, 12));

const sentimentScore = computed(() => {
  const pos = Number(sentiment.value.positive || 0);
  const neg = Number(sentiment.value.negative || 0);
  return Math.round(Math.max(0, Math.min(100, 50 + (pos - neg) / 2)));
});

// LLM 洞察欄位（相容物件/字串）。
function topicText(item) {
  if (typeof item === "string") return item;
  return item?.topic || item?.pain_point || item?.title || "";
}
function topicMeaning(item) {
  if (!item || typeof item === "string") return "";
  return item.meaning || item.reason || "";
}

const hotTopics = computed(() => state.insight?.hot_topics || []);
const painPoints = computed(() => state.insight?.consumer_pain_points || []);
const suggestions = computed(() => state.insight?.marketing_suggestions || []);

async function fetchReport() {
  state.loading = true;
  state.errorMessage = "";

  try {
    const [dashboardResp, insightResp] = await Promise.all([
      api.get("/api/dashboard/full", { params: { keyword: keyword.value, days: days.value } }),
      api.get("/api/analysis/keyword", {
        params: { keyword: keyword.value, analysis_type: "overview", days: days.value },
      }),
    ]);

    state.dashboard = dashboardResp.data.data;
    state.insight = insightResp.data.result?.data || null;
  } catch (error) {
    console.error(error);
    state.errorMessage = "報告資料載入失敗，請確認 backend 是否正在執行。";
  } finally {
    state.loading = false;
  }
}

function printReport() {
  window.print();
}

onMounted(fetchReport);
</script>

<template>
  <div class="report-view">
    <!-- 工具列（列印時隱藏） -->
    <div class="report-toolbar">
      <button type="button" class="report-back" @click="router.back()">← 返回</button>
      <button type="button" class="report-print" @click="printReport">列印 / 存成 PDF</button>
    </div>

    <p v-if="state.errorMessage" class="error-message">{{ state.errorMessage }}</p>
    <p v-else-if="state.loading" class="report-loading">報告產生中…</p>

    <article v-else class="report-doc">
      <!-- 標題 -->
      <header class="report-head">
        <div class="report-brand">
          <LogoMark :size="40" />
          <div>
            <strong>MeBOD 醫美輿情分析報告</strong>
            <span>Medical Beauty Opinion Report</span>
          </div>
        </div>
        <div class="report-meta">
          <p>關鍵字：<strong>{{ keyword }}</strong></p>
          <p>期間：近 {{ days }} 天</p>
          <p>產生時間：{{ generatedAt }}</p>
        </div>
      </header>

      <!-- 總覽指標 -->
      <section class="report-section">
        <h3>一、輿情總覽</h3>
        <div class="report-stat-grid">
          <div><span>相關文章</span><strong>{{ overview.total_articles || 0 }}</strong></div>
          <div><span>情緒分數</span><strong>{{ sentimentScore }}</strong></div>
          <div><span>負面比例</span><strong>{{ sentiment.negative || 0 }}%</strong></div>
          <div><span>成長率</span><strong>{{ overview.growth_rate || 0 }}%</strong></div>
        </div>
        <div class="report-senti-bar">
          <div class="seg pos" :style="{ width: `${sentiment.positive || 0}%` }"></div>
          <div class="seg neu" :style="{ width: `${sentiment.neutral || 0}%` }"></div>
          <div class="seg neg" :style="{ width: `${sentiment.negative || 0}%` }"></div>
        </div>
        <p class="report-senti-legend">
          正面 {{ sentiment.positive || 0 }}%　中性 {{ sentiment.neutral || 0 }}%　負面 {{ sentiment.negative || 0 }}%
        </p>
      </section>

      <!-- LLM 摘要 -->
      <section v-if="state.insight" class="report-section">
        <h3>二、整體摘要</h3>
        <p class="report-summary">{{ state.insight.summary || "尚無摘要。" }}</p>
      </section>

      <!-- 熱門話題 + 痛點 -->
      <section v-if="hotTopics.length || painPoints.length" class="report-section report-two-col">
        <div>
          <h4>熱門話題</h4>
          <ul>
            <li v-for="(item, i) in hotTopics" :key="`t${i}`">
              <strong>{{ topicText(item) }}</strong>
              <span v-if="topicMeaning(item)">{{ topicMeaning(item) }}</span>
            </li>
          </ul>
        </div>
        <div>
          <h4>消費者痛點</h4>
          <ul>
            <li v-for="(item, i) in painPoints" :key="`p${i}`">
              <strong>{{ topicText(item) }}</strong>
              <span v-if="topicMeaning(item)">{{ topicMeaning(item) }}</span>
            </li>
          </ul>
        </div>
      </section>

      <!-- 行銷建議 -->
      <section v-if="suggestions.length" class="report-section">
        <h3>三、行銷建議</h3>
        <ol class="report-suggestions">
          <li v-for="(s, i) in suggestions" :key="`s${i}`">
            <strong>{{ typeof s === "string" ? s : s.title }}</strong>
            <span v-if="typeof s !== 'string' && s.what">{{ s.what }}</span>
            <small v-if="typeof s !== 'string' && (s.where || s.when)">
              {{ [s.where, s.when].filter(Boolean).join("｜") }}
            </small>
          </li>
        </ol>
      </section>

      <!-- 熱門文章 -->
      <section v-if="hotArticles.length" class="report-section">
        <h3>四、熱門文章</h3>
        <ul class="report-articles">
          <li v-for="article in hotArticles" :key="article.id">
            <strong>{{ article.title }}</strong>
            <small>{{ article.board }} · 推 {{ article.push_count }}</small>
          </li>
        </ul>
      </section>

      <!-- 熱門關鍵字 -->
      <section v-if="keywords.length" class="report-section">
        <h3>五、熱門關鍵字</h3>
        <div class="report-keywords">
          <span v-for="kw in keywords" :key="kw.keyword || kw.word">
            {{ kw.keyword || kw.word }}<em v-if="kw.count"> ×{{ kw.count }}</em>
          </span>
        </div>
      </section>

      <footer class="report-foot">
        <span>MeBOD 醫美時尚輿情分析系統 · 115405 專題製作</span>
        <span>資料來源：PTT</span>
      </footer>
    </article>
  </div>
</template>
