<template>
  <div>
    <el-page-header @back="$router.push('/products')">
      <template #content>
        <span>{{ product?.name || '价格走势' }}</span>
      </template>
    </el-page-header>
    <el-card style="margin-top: 16px">
      <div v-if="history.length > 0" class="chart-container">
        <canvas ref="chartRef"></canvas>
      </div>
      <el-empty v-else description="暂无价格记录" />

      <el-table :data="history" stripe size="small" style="margin-top: 16px">
        <el-table-column prop="price" label="价格" width="100">
          <template #default="{ row }">¥{{ row.price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="原价" width="100">
          <template #default="{ row }">{{ row.original_price ? '¥' + row.original_price.toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="timestamp" label="时间" min-width="160" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from "vue";
import { useRoute } from "vue-router";
import Chart from "chart.js/auto";
import * as api from "../api";

const props = defineProps({ id: [String, Number] });
const route = useRoute();
const productId = computed(() => Number(props.id || route.params.id));
const product = ref(null);
const history = ref([]);
const chartRef = ref(null);
let chart = null;

async function load() {
  try {
    const [pr, hr] = await Promise.all([api.getProduct(productId.value), api.getHistory(productId.value)]);
    product.value = pr.data;
    history.value = hr.data;
    drawChart();
  } catch (e) {
    product.value = null;
    history.value = [];
  }
}

function drawChart() {
  if (chart) chart.destroy();
  if (!chartRef.value || history.value.length < 2) return;

  const labels = history.value.map((r) => r.timestamp.slice(0, 10)).reverse();
  const prices = history.value.map((r) => r.price).reverse();
  const min = Math.min(...prices) * 0.98;
  const max = Math.max(...prices) * 1.02;

  chart = new Chart(chartRef.value, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "价格",
          data: prices,
          borderColor: "#409eff",
          backgroundColor: "rgba(64,158,255,0.1)",
          fill: true,
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        y: { min, max, ticks: { callback: (v) => "¥" + v } },
      },
    },
  });
}

onMounted(load);
watch(productId, load);
</script>

<style scoped>
.chart-container {
  width: 100%;
  max-height: 360px;
}
</style>
