<!-- frontend/src/components/InsightPanel.vue -->

<script setup>
import { computed } from "vue";

const props = defineProps({
  insight: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const topicItems = computed(() => props.insight?.hot_topics || []);
const painItems = computed(() => props.insight?.consumer_pain_points || []);

const suggestionItems = computed(() => {
  return (
    props.insight?.marketing_suggestions ||
    props.insight?.recommended_actions ||
    props.insight?.improvement_actions ||
    []
  );
});

function itemKey(item, fallback) {
  if (typeof item === "string") return item;

  return item?.title || item?.topic || item?.pain_point || fallback;
}

function itemTitle(item, fallback = "") {
  if (typeof item === "string") return item;

  return item?.topic || item?.pain_point || item?.title || fallback;
}

function itemMeaning(item) {
  if (!item || typeof item === "string") return "";

  return item.meaning || item.reason || "";
}

function suggestionDetailRows(suggestion) {
  if (!suggestion || typeof suggestion === "string") return [];

  const rows = [
    ["根據", suggestion.based_on],
    ["做什麼", suggestion.what],
    ["為什麼", suggestion.why],
    ["誰來做", suggestion.who],
    ["在哪裡", suggestion.where],
    ["何時", suggestion.when],
    ["怎麼做", suggestion.how],
    ["投入", suggestion.how_much],
    ["預期成效", suggestion.expected_effect],
  ];

  return rows.filter(([, value]) => value);
}
</script>

<template>
  <section class="card insight-card">
    <h2 class="section-title">LLM 洞察分析</h2>

    <div v-if="loading">
      <div class="skeleton insight-skeleton"></div>
      <div class="skeleton insight-skeleton small"></div>
    </div>

    <div v-else-if="!insight" class="empty-state">
      尚未取得 LLM 分析資料。
    </div>

    <div v-else>
      <p class="insight-summary">
        {{ insight.summary || insight.trend_summary || "目前沒有摘要。" }}
      </p>

      <div class="insight-block">
        <h3>熱門話題</h3>
        <ul class="insight-detail-list">
          <li v-for="(topic, index) in topicItems" :key="itemKey(topic, index)">
            <strong>↑ {{ itemTitle(topic, `話題 ${index + 1}`) }}</strong>
            <span v-if="itemMeaning(topic)">{{ itemMeaning(topic) }}</span>
          </li>
        </ul>
      </div>

      <div class="insight-block">
        <h3>消費者痛點</h3>
        <ul class="insight-detail-list">
          <li v-for="(pain, index) in painItems" :key="itemKey(pain, index)">
            <strong>! {{ itemTitle(pain, `痛點 ${index + 1}`) }}</strong>
            <span v-if="itemMeaning(pain)">{{ itemMeaning(pain) }}</span>
          </li>
        </ul>
      </div>

      <div class="insight-block">
        <h3>行銷建議</h3>
        <div class="insight-suggestion-list">
          <article
            v-for="(suggestion, index) in suggestionItems"
            :key="itemKey(suggestion, index)"
            class="insight-suggestion-card"
          >
            <template v-if="typeof suggestion === 'string'">
              i {{ suggestion }}
            </template>

            <template v-else>
              <div class="insight-suggestion-head">
                <span v-if="suggestion.category">{{ suggestion.category }}</span>
                <strong>{{ suggestion.title || `建議 ${index + 1}` }}</strong>
              </div>

              <dl>
                <template
                  v-for="[label, value] in suggestionDetailRows(suggestion)"
                  :key="label"
                >
                  <dt>{{ label }}</dt>
                  <dd>{{ value }}</dd>
                </template>
              </dl>
            </template>
          </article>
        </div>
      </div>

    </div>
  </section>
</template>
