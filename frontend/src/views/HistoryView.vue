<!-- frontend/src/views/HistoryView.vue -->

<script setup>
import { computed, onMounted, reactive, ref } from "vue";

import api from "../services/api.js";
import { useAuth } from "../composables/useAuth";

const { isAuthenticated } = useAuth();

const tabs = [
  { id: "list", label: "歷史列表" },
  { id: "compare", label: "並排比較" },
  { id: "trend", label: "趨勢圖" },
];

// 分析類型英文轉繁中標籤。
const ANALYSIS_TYPE_LABELS = {
  overview: "綜合分析",
  trend: "趨勢分析",
  sentiment: "情緒分析",
};

function analysisTypeLabel(type) {
  return ANALYSIS_TYPE_LABELS[type] || type;
}

const state = reactive({
  activeTab: "list",
  loading: false,
  errorMessage: "",
  records: [],
});

const selectedIds = ref([]);
const starredIds = ref(JSON.parse(localStorage.getItem("history-starred-ids") || "[]"));
const historyPage = ref(1);
const historyPageSize = 15;
const searchText = ref("");
const showStarredOnly = ref(false);

const sortedRecords = computed(() => {
  return [...state.records].sort((a, b) => {
    const aStar = starredIds.value.includes(a.id) ? 1 : 0;
    const bStar = starredIds.value.includes(b.id) ? 1 : 0;

    if (aStar !== bStar) return bStar - aStar;

    return new Date(b.created_at || 0) - new Date(a.created_at || 0);
  });
});

// 依關鍵字搜尋與「只看已加星」篩選後的清單。
const filteredRecords = computed(() => {
  const keyword = searchText.value.trim().toLowerCase();

  return sortedRecords.value.filter((record) => {
    const matchKeyword = !keyword || (record.keyword || "").toLowerCase().includes(keyword);
    const matchStar = !showStarredOnly.value || starredIds.value.includes(record.id);
    return matchKeyword && matchStar;
  });
});

const selectedRecords = computed(() => {
  return selectedIds.value
    .map((id) => state.records.find((record) => record.id === id))
    .filter(Boolean);
});

const historyTotalPages = computed(() => {
  return Math.max(1, Math.ceil(filteredRecords.value.length / historyPageSize));
});

const pagedHistoryRecords = computed(() => {
  const page = Math.min(historyPage.value, historyTotalPages.value);
  const start = (page - 1) * historyPageSize;
  return filteredRecords.value.slice(start, start + historyPageSize);
});

function resetHistoryPage() {
  historyPage.value = 1;
}

const comparePair = computed(() => {
  return selectedRecords.value.length === 2
    ? selectedRecords.value
    : sortedRecords.value.slice(0, 2);
});

const comparison = computed(() => {
  const [previous, current] = comparePair.value;

  if (!previous || !current) return [];

  return [
    {
      label: "文章數",
      previous: previous.article_count,
      current: current.article_count,
      unit: "篇",
      direction: current.article_count - previous.article_count,
    },
    {
      label: "情緒分數",
      previous: previous.sentiment_score,
      current: current.sentiment_score,
      unit: "分",
      direction: current.sentiment_score - previous.sentiment_score,
    },
    {
      label: "負面比例",
      previous: previous.negative_ratio,
      current: current.negative_ratio,
      unit: "%",
      direction: previous.negative_ratio - current.negative_ratio,
      inverse: true,
    },
  ];
});

const topicComparison = computed(() => {
  const [previous, current] = comparePair.value;

  if (!previous || !current) {
    return {
      newTopics: [],
      cooledTopics: [],
      sharedTopics: [],
    };
  }

  const previousTopics = previous.topics || [];
  const currentTopics = current.topics || [];

  return {
    newTopics: currentTopics.filter((topic) => !previousTopics.includes(topic)),
    cooledTopics: previousTopics.filter((topic) => !currentTopics.includes(topic)),
    sharedTopics: currentTopics.filter((topic) => previousTopics.includes(topic)),
  };
});

const trendRecords = computed(() => {
  return [...state.records]
    .filter((record) => record.created_at)
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    .slice(-12);
});

const trendStats = computed(() => {
  const records = trendRecords.value;
  const scores = records.map((record) => record.sentiment_score);

  if (!records.length) {
    return {
      latest: 0,
      highest: 0,
      lowest: 0,
      count: 0,
    };
  }

  return {
    latest: scores[scores.length - 1],
    highest: Math.max(...scores),
    lowest: Math.min(...scores),
    count: records.length,
  };
});

const scorePolyline = computed(() => buildPolyline("sentiment_score", false));
const negativePolyline = computed(() => buildPolyline("negative_ratio"));

// 圖上資料點（HTML overlay），帶 tooltip 顯示數值與日期。
// 用 % 定位，和 SVG 的 0~100 座標一致。
const trendPoints = computed(() => {
  const records = trendRecords.value;
  const total = records.length;

  if (total === 0) return [];

  return records.map((record, index) => {
    const x = total === 1 ? 50 : (index / (total - 1)) * 100;
    const score = Math.max(0, Math.min(100, Number(record.sentiment_score || 0)));
    const neg = Math.max(0, Math.min(100, Number(record.negative_ratio || 0)));
    const dateLabel = formatDate(record.created_at).slice(5, 10);

    return {
      id: record.id,
      x,
      // 分數越高越靠上（y 越小）；負面越低越靠上，和折線一致。
      scoreY: 100 - score,
      negativeY: neg,
      score,
      negative: neg,
      dateLabel,
    };
  });
});

function formatDate(value) {
  if (!value) return "-";

  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function getScoreClass(score) {
  if (score >= 75) return "good";
  if (score >= 55) return "neutral";
  return "bad";
}

function getNegativeClass(ratio) {
  if (ratio <= 10) return "good";
  if (ratio <= 30) return "neutral";
  return "bad";
}

function toggleRecord(recordId) {
  if (selectedIds.value.includes(recordId)) {
    selectedIds.value = selectedIds.value.filter((id) => id !== recordId);
    return;
  }

  selectedIds.value = [...selectedIds.value.slice(-1), recordId];
}

function toggleStar(recordId) {
  if (starredIds.value.includes(recordId)) {
    starredIds.value = starredIds.value.filter((id) => id !== recordId);
  } else {
    starredIds.value = [...starredIds.value, recordId];
  }

  localStorage.setItem("history-starred-ids", JSON.stringify(starredIds.value));
}

async function deleteRecord(recordId) {
  if (!window.confirm("確定要刪除這筆分析紀錄嗎？此動作無法復原。")) return;

  try {
    await api.delete(`/api/analysis/history/${recordId}`);
    state.records = state.records.filter((record) => record.id !== recordId);
    selectedIds.value = selectedIds.value.filter((id) => id !== recordId);
    starredIds.value = starredIds.value.filter((id) => id !== recordId);
    localStorage.setItem("history-starred-ids", JSON.stringify(starredIds.value));
  } catch (error) {
    console.error(error);
    state.errorMessage = error.response?.status === 401
      ? "刪除紀錄需要登入。"
      : "刪除失敗，請稍後再試。";
  }
}

function goToCompare() {
  if (selectedIds.value.length === 2) {
    state.activeTab = "compare";
  }
}

function getDirectionClass(item) {
  if (item.direction === 0) return "same";

  return item.direction > 0 ? "up" : "down";
}

function getDirectionIcon(item) {
  if (item.direction === 0) return "→";

  return item.direction > 0 ? "↑" : "↓";
}

function buildPolyline(key, invert = false) {
  const records = trendRecords.value;

  if (records.length === 0) return "";
  if (records.length === 1) {
    const y = 100 - Math.max(0, Math.min(100, Number(records[0][key] || 0)));
    return `0,${y} 100,${y}`;
  }

  return records
    .map((record, index) => {
      const x = (index / (records.length - 1)) * 100;
      const rawValue = Math.max(0, Math.min(100, Number(record[key] || 0)));
      const value = invert ? 100 - rawValue : rawValue;
      const y = 100 - value;

      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

async function fetchHistory() {
  state.loading = true;
  state.errorMessage = "";

  try {
    const response = await api.get("/api/analysis/history", {
      params: { limit: 80 },
    });

    state.records = response.data.data?.records || [];
    selectedIds.value = state.records.slice(0, 2).map((record) => record.id);
  } catch (error) {
    console.error(error);
    state.errorMessage = "歷史紀錄載入失敗，請確認 backend 是否已重新啟動。";
  } finally {
    state.loading = false;
  }
}

onMounted(fetchHistory);
</script>

<template>
  <section class="history-page">
    <div class="history-header">
      <div>
        <h2>分析歷史</h2>
        <p>查看每次分析結果、比較口碑變化，並追蹤長期情緒趨勢。</p>
      </div>

      <div class="history-tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          :class="{ active: state.activeTab === tab.id }"
          @click="state.activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <p v-if="state.errorMessage" class="error-message">
      {{ state.errorMessage }}
    </p>

    <section v-if="state.activeTab === 'list'" class="history-panel">
      <div class="history-panel-header">
        <div>
          <h3>歷史列表</h3>
          <p>勾選兩筆記錄後即可進入並排比較。</p>
        </div>
      </div>

      <div class="history-toolbar">
        <input
          v-model="searchText"
          class="history-search"
          type="text"
          placeholder="🔍 搜尋關鍵字"
          @input="resetHistoryPage"
        />
        <label class="history-star-filter">
          <input v-model="showStarredOnly" type="checkbox" @change="resetHistoryPage" />
          只看已加星
        </label>
      </div>

      <div v-if="state.loading" class="skeleton history-skeleton"></div>

      <div v-else class="history-table-wrap">
        <table class="history-table">
          <thead>
            <tr>
              <th>選取</th>
              <th>重要</th>
              <th>日期</th>
              <th>關鍵字</th>
              <th>文章數</th>
              <th>情緒分數</th>
              <th>負面比例</th>
              <th>摘要</th>
              <th v-if="isAuthenticated">操作</th>
            </tr>
          </thead>

          <tbody>
            <tr v-for="record in pagedHistoryRecords" :key="record.id">
              <td>
                <input
                  type="checkbox"
                  :aria-label="`選取 ${record.keyword}`"
                  :checked="selectedIds.includes(record.id)"
                  @change="toggleRecord(record.id)"
                />
              </td>
              <td>
                <button
                  class="history-star-button"
                  type="button"
                  :aria-label="starredIds.includes(record.id) ? '取消加星' : '加星'"
                  :class="{ active: starredIds.includes(record.id) }"
                  @click="toggleStar(record.id)"
                >
                  ★
                </button>
              </td>
              <td>{{ formatDate(record.created_at) }}</td>
              <td>
                <strong>{{ record.keyword }}</strong>
                <small>{{ record.days }} 天 · {{ analysisTypeLabel(record.analysis_type) }}</small>
              </td>
              <td>{{ record.article_count }}</td>
              <td>
                <span :class="['history-score-pill', getScoreClass(record.sentiment_score)]">
                  {{ record.sentiment_score }}
                </span>
                <small
                  v-if="record.ai_rated_percent != null"
                  class="history-coverage"
                  title="AI 逐篇評分的覆蓋率，越高分數越可信"
                >AI {{ record.ai_rated_percent }}%</small>
              </td>
              <td>
                <span :class="['history-score-pill', getNegativeClass(record.negative_ratio)]">
                  {{ record.negative_ratio }}%
                </span>
              </td>
              <td class="history-summary-cell">{{ record.summary }}</td>
              <td v-if="isAuthenticated">
                <button
                  class="history-delete-button"
                  type="button"
                  aria-label="刪除紀錄"
                  @click="deleteRecord(record.id)"
                >
                  刪除
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="!filteredRecords.length" class="empty-state">
          {{ state.records.length ? "沒有符合條件的紀錄。" : "尚無歷史分析紀錄。" }}
        </div>
      </div>

      <div v-if="filteredRecords.length > historyPageSize" class="history-pagination">
        <div>
          <button
            type="button"
            :disabled="historyPage <= 1"
            @click="historyPage -= 1"
          >
            ‹
          </button>
          <span>{{ historyPage }} / {{ historyTotalPages }}</span>
          <button
            type="button"
            :disabled="historyPage >= historyTotalPages"
            @click="historyPage += 1"
          >
            ›
          </button>
        </div>
        <span>每頁最多 {{ historyPageSize }} 筆，共 {{ filteredRecords.length }} 筆</span>
      </div>

      <div v-if="selectedIds.length === 2" class="compare-hint-bar">
        <span>已選擇 2 筆記錄，可以進行並排比較。</span>
        <button type="button" @click="goToCompare">前往比較</button>
      </div>
    </section>

    <section v-if="state.activeTab === 'compare'" class="history-panel">
      <div class="history-panel-header">
        <div>
          <h3>並排比較</h3>
          <p>左右並排查看兩次分析，中間顯示每個指標的變化方向。</p>
        </div>
      </div>

      <div v-if="comparePair.length < 2" class="empty-state">
        請先在歷史列表選擇兩筆記錄。
      </div>

      <div v-else class="compare-grid">
        <article class="compare-record-card">
          <span>上次分析</span>
          <h4>{{ comparePair[0].keyword }}</h4>
          <p>{{ formatDate(comparePair[0].created_at) }}</p>
          <strong>{{ comparePair[0].sentiment_score }} 分</strong>
          <small>{{ comparePair[0].summary }}</small>
        </article>

        <div class="compare-delta-card">
          <div
            v-for="item in comparison"
            :key="item.label"
            :class="['compare-delta-row', getDirectionClass(item)]"
          >
            <span>{{ item.label }}</span>
            <strong>{{ getDirectionIcon(item) }}</strong>
            <em>
              {{ item.previous }}{{ item.unit }} → {{ item.current }}{{ item.unit }}
            </em>
          </div>
        </div>

        <article class="compare-record-card current">
          <span>本次分析</span>
          <h4>{{ comparePair[1].keyword }}</h4>
          <p>{{ formatDate(comparePair[1].created_at) }}</p>
          <strong>{{ comparePair[1].sentiment_score }} 分</strong>
          <small>{{ comparePair[1].summary }}</small>
        </article>
      </div>

      <div class="topic-compare-grid">
        <article class="topic-compare-card new">
          <h4>新出現話題</h4>
          <p>代表新的行銷機會</p>
          <div>
            <span v-for="topic in topicComparison.newTopics" :key="topic">{{ topic }}</span>
            <em v-if="!topicComparison.newTopics.length">暫無新話題</em>
          </div>
        </article>

        <article class="topic-compare-card cooled">
          <h4>消失話題</h4>
          <p>代表話題正在退燒</p>
          <div>
            <span v-for="topic in topicComparison.cooledTopics" :key="topic">{{ topic }}</span>
            <em v-if="!topicComparison.cooledTopics.length">暫無退燒話題</em>
          </div>
        </article>

        <article class="topic-compare-card shared">
          <h4>持續話題</h4>
          <p>代表需要持續關注</p>
          <div>
            <span v-for="topic in topicComparison.sharedTopics" :key="topic">{{ topic }}</span>
            <em v-if="!topicComparison.sharedTopics.length">暫無共同話題</em>
          </div>
        </article>
      </div>
    </section>

    <section v-if="state.activeTab === 'trend'" class="history-panel">
      <div class="history-panel-header">
        <div>
          <h3>趨勢圖</h3>
          <p>以多次分析紀錄追蹤情緒分數與負面比例變化。</p>
        </div>
      </div>

      <div class="history-trend-chart">
        <div class="history-chart-legend">
          <span class="score">情緒分數</span>
          <span class="negative">負面比例</span>
        </div>

        <div v-if="!trendPoints.length" class="empty-state">
          尚無足夠紀錄可繪製趨勢。
        </div>

        <div v-else class="history-chart-body">
          <div class="history-chart-yaxis">
            <span>100</span>
            <span>50</span>
            <span>0</span>
          </div>

          <div class="history-chart-plot">
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="情緒分數與負面比例趨勢圖">
              <line x1="0" y1="0" x2="100" y2="0" />
              <line x1="0" y1="50" x2="100" y2="50" />
              <line x1="0" y1="100" x2="100" y2="100" />
              <polyline class="score-line" :points="scorePolyline" />
              <polyline class="negative-line" :points="negativePolyline" />
            </svg>

            <!-- HTML 資料點 overlay：避免被 SVG 拉伸變形，並提供 tooltip。 -->
            <span
              v-for="point in trendPoints"
              :key="`s-${point.id}`"
              class="chart-dot score-dot"
              :style="{ left: `${point.x}%`, top: `${point.scoreY}%` }"
              :title="`${point.dateLabel}｜情緒分數 ${point.score}`"
            ></span>
            <span
              v-for="point in trendPoints"
              :key="`n-${point.id}`"
              class="chart-dot negative-dot"
              :style="{ left: `${point.x}%`, top: `${point.negativeY}%` }"
              :title="`${point.dateLabel}｜負面比例 ${point.negative}%`"
            ></span>
          </div>
        </div>

        <div v-if="trendPoints.length" class="history-chart-labels">
          <span v-for="record in trendRecords" :key="record.id">
            {{ formatDate(record.created_at).slice(5, 10) }}
          </span>
        </div>
      </div>

      <div class="history-stat-grid">
        <article>
          <span>最新分數</span>
          <strong>{{ trendStats.latest }}</strong>
        </article>
        <article>
          <span>最高分</span>
          <strong>{{ trendStats.highest }}</strong>
        </article>
        <article>
          <span>最低分</span>
          <strong>{{ trendStats.lowest }}</strong>
        </article>
        <article>
          <span>分析次數</span>
          <strong>{{ trendStats.count }}</strong>
        </article>
      </div>
    </section>
  </section>
</template>
