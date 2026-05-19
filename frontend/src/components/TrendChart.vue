<!-- frontend/src/components/TrendChart.vue -->

<script setup>
import { onMounted, watch, ref } from "vue";
import Chart from "chart.js/auto";

const props = defineProps({
  trend: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
});

const canvasRef = ref(null);
let chartInstance = null;


// Note:
// Hàm này dùng để vẽ hoặc vẽ lại biểu đồ.
// Mỗi lần trend data thay đổi thì destroy chart cũ rồi tạo chart mới.
function renderChart() {
  if (!canvasRef.value) return;

  if (chartInstance) {
    chartInstance.destroy();
  }

  const labels = props.trend.map((item) => item.date);
  const values = props.trend.map((item) => item.count);

  chartInstance = new Chart(canvasRef.value, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "每日文章數",
          data: values,
          borderWidth: 2,
          tension: 0.35,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,

      // Note:
      // plugins 控制圖表上方 legend 顯示。
      plugins: {
        legend: {
          display: true,
        },
      },

      // Note:
      // scales 控制 X / Y 軸格式。
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            precision: 0,
          },
        },
      },
    },
  });
}

onMounted(() => {
  renderChart();
});

watch(
  () => props.trend,
  () => {
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