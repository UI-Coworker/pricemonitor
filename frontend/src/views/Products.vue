<template>
  <div>
    <el-row :gutter="20" class="stats-row">
      <el-col :span="8">
        <el-card shadow="hover">
          <el-statistic title="监控中" :value="products.length" suffix="件" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover">
          <el-statistic title="总价值" :value="totalValue" prefix="¥" :precision="0" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="alert-count">
          <el-statistic title="已降价" :value="alertCount" suffix="件" :value-style="{ color: '#f56c6c' }" />
        </el-card>
      </el-col>
    </el-row>

    <el-card class="actions-card">
      <el-space>
        <el-button type="primary" :loading="syncing" @click="doSync">同步购物车</el-button>
        <el-button type="success" :loading="checking" @click="doCheck">立即检查</el-button>
      </el-space>
    </el-card>

    <el-card v-if="alerts.length > 0" class="alert-card">
      <template #header><span style="color: #f56c6c">降价提醒</span></template>
      <el-table :data="alerts" stripe size="small">
        <el-table-column prop="name" label="商品" min-width="160" show-overflow-tooltip />
        <el-table-column label="现价" width="100">
          <template #default="{ row }">¥{{ row.current_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="目标价" width="100">
          <template #default="{ row }">¥{{ row.target_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="降幅" width="100">
          <template #default="{ row }">
            <span style="color: #f56c6c">-¥{{ (row.target_price - row.current_price).toFixed(2) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>商品列表</span>
          <el-button type="primary" @click="store.loadProducts()">刷新</el-button>
        </div>
      </template>
      <el-table :data="store.products" stripe v-loading="store.loading">
        <el-table-column prop="name" label="商品名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="现价" width="100">
          <template #default="{ row }">¥{{ row.current_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="原价" width="100">
          <template #default="{ row }">{{ row.original_price ? '¥' + row.original_price.toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column label="目标价" width="190">
          <template #default="{ row }">
            <template v-if="editingId === row.id">
              <el-input-number v-model="editingTarget" :min="0" :precision="2" size="small" style="width:120px" />
              <el-button size="small" type="primary" @click="saveTarget(row)">确定</el-button>
              <el-button size="small" @click="editingId = null">取消</el-button>
            </template>
            <template v-else>
              <span>{{ row.target_price ? '¥' + row.target_price.toFixed(2) : '未设置' }}</span>
              <el-button size="small" style="margin-left:8px" @click="editTarget(row)">设置</el-button>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push('/history/' + row.id)">价格走势</el-button>
            <el-popconfirm title="确定移除此商品吗？" @confirm="store.removeProduct(row.id)">
              <template #reference>
                <el-button size="small" type="danger" plain>移除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { useProductStore } from "../stores/products";

const store = useProductStore();
const syncing = ref(false);
const checking = ref(false);
const editingId = ref(null);
const editingTarget = ref(0);

const products = computed(() => store.products);
const totalValue = computed(() => store.products.reduce((s, p) => s + p.current_price, 0));
const alertCount = computed(
  () => store.products.filter((p) => p.target_price && p.current_price <= p.target_price).length
);
const alerts = computed(() =>
  store.products.filter((p) => p.target_price && p.current_price <= p.target_price)
);

async function doSync() {
  syncing.value = true;
  try { await store.syncCart(); } finally { syncing.value = false; }
}

async function doCheck() {
  checking.value = true;
  try { await store.checkPrices(); } finally { checking.value = false; }
}

function editTarget(row) {
  editingId.value = row.id;
  editingTarget.value = row.target_price || 0;
}

async function saveTarget(row) {
  await store.setTarget(row.id, editingTarget.value || null);
  editingId.value = null;
}

store.loadProducts();
</script>

<style scoped>
.stats-row { margin-bottom: 20px; }
.actions-card { margin-bottom: 20px; }
.alert-card { margin-bottom: 20px; border-color: #f56c6c; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
