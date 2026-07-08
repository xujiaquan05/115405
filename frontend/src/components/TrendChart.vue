<!-- frontend/src/components/TrendChart.vue -->

<script setup>
import { nextTick, onMounted, watch, ref } from "vue";
import Chart from "chart.js/auto";

const props = defineProps({
  trend: {
    type: Array,
    default: () => [],
  },
  keywordTrends: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  keyword: {
    type: String,
    default: "",
  },
});

const canvasRef = ref(null);
let chartInstance = null;
const Y_AXIS_MAX = 25;
const Y_AXIS_STEP = 5;

const LINE_COLORS = [
  "#f25549",
  "#2563eb",
  "#16a34a",
  "#9333ea",
  "#f59e0b",
  "#0d9488",
  "#db2777",
  "#4f46e5",
  "#84cc16",
  "#0891b2",
];

function splitKeywords(keyword) {
  return (keyword || "")
    .split(/[,\s、，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function hashKeyword(keyword) {
  return Array.from(keyword).reduce((hash, char) => {
    return (hash * 31 + char.charCodeAt(0)) % 360;
  }, 17);
}

function getKeywordColor(keyword, index) {
  if (index < LINE_COLORS.length) {
    return LINE_COLORS[index];
  }

  const hue = (hashKeyword(keyword) + index * 137) % 360;
  return `hsl(${hue}, 76%, 52%)`;
}

function buildFallbackSeries() {
  const label = props.keyword?.trim() || "搜尋關鍵字";

  return [
    {
      keyword: label,
      trend: props.trend,
    },
  ];
}

function getSeries() {
  if (props.keywordTrends.length > 0) {
    return props.keywordTrends;
  }

  return buildFallbackSeries();
}

function getLabels(series) {
  const dateSet = new Set();

  series.forEach((item) => {
    item.trend.forEach((point) => {
      dateSet.add(point.date);
    });
  });

  return Array.from(dateSet).sort();
}

function buildDataset(seriesItem, labels, index) {
  const countByDate = new Map(
    seriesItem.trend.map((point) => [point.date, point.count])
  );
  const color = getKeywordColor(seriesItem.keyword, index);

  return {
    label: seriesItem.keyword,
    data: labels.map((date) => countByDate.get(date) || 0),
    borderColor: color,
    backgroundColor: color,
    borderWidth: 2.4,
    pointRadius: 0,
    pointHoverRadius: 4,
    pointHoverBackgroundColor: color,
    pointHoverBorderColor: "#ffffff",
    pointHoverBorderWidth: 2,
    tension: 0.14,
  };
}

// 繪製或重新繪製圖表。
// 每次 trend data 變動時，先 destroy 舊圖再建立新圖。
function renderChart() {
  if (!canvasRef.value || props.loading) return;

  if (chartInstance) {
    chartInstance.destroy();
  }

  const rawSeries = getSeries();
  const selectedKeywords = splitKeywords(props.keyword);
  const series = rawSeries.filter((item) => {
    return selectedKeywords.length === 0 || selectedKeywords.includes(item.keyword);
  });
  const visibleSeries = series.length > 0 ? series : rawSeries;
  const labels = getLabels(visibleSeries);
  const datasets = visibleSeries.map((seriesItem, index) => {
    return buildDataset(seriesItem, labels, index);
  });
  chartInstance = new Chart(canvasRef.value, {
    type: "line",
    data: {
      labels,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,

      // Note:
      // plugins 控制圖表上方 legend 顯示。
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          align: "center",
          labels: {
            boxWidth: 34,
            boxHeight: 2,
            color: "#374151",
            font: {
              size: 13,
              weight: "700",
            },
          },
        },
        tooltip: {
          mode: "index",
          intersect: false,
          callbacks: {
            label: (context) => `${context.dataset.label}: ${context.parsed.y} 則`,
          },
        },
      },

      // Note:
      // scales 控制 X / Y 軸格式。
      scales: {
        y: {
          display: true,
          beginAtZero: true,
          max: Y_AXIS_MAX,
          title: {
            display: true,
            text: "則數",
            color: "#6b7280",
            font: {
              size: 13,
              weight: "700",
            },
          },
          ticks: {
            precision: 0,
            stepSize: Y_AXIS_STEP,
            color: "#6b7280",
            padding: 10,
          },
          grid: {
            color: "#e5e7eb",
            drawBorder: false,
          },
        },
        x: {
          ticks: {
            color: "#6b7280",
            maxRotation: 45,
            minRotation: 45,
            autoSkip: true,
            maxTicksLimit: 24,
          },
          grid: {
            display: false,
          },
        },
      },
      interaction: {
        mode: "index",
        intersect: false,
      },
    },
  });
}

onMounted(async () => {
  await nextTick();
  renderChart();
});

watch(
  () => [props.trend, props.keywordTrends, props.loading, props.keyword],
  async () => {
    await nextTick();
    renderChart();
  },
  { deep: true }
);
</script>

<template>
  <section class="card chart-card">
    <h2 class="section-title">討論趨勢</h2>

    <div v-if="loading" class="skeleton chart-skeleton"></div>

    <div v-else class="chart-wrapper">
      <canvas ref="canvasRef"></canvas>
    </div>
  </section>
</template>
