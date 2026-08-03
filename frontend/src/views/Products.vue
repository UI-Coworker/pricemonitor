<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>商品管理</span>
          <el-button type="primary" @click="store.loadProducts()">刷新</el-button>
        </div>
      </template>
      <el-table :data="store.products" stripe v-loading="store.loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="商品名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="现价" width="100">
          <template #default="{ row }">¥{{ row.current_price.toFixed(2) }}</template>
        </el-table-column>
        <el-table-column label="原价" width="100">
          <template #default="{ row }">{{ row.original_price ? '¥' + row.original_price.toFixed(2) : '-' }}</template>
        </el-table-column>
        <el-table-column label="目标价" width="180">
          <template #default="{ row }">
            <template v-if="editingId === row.id">
              <el-input-number v-model="editingTarget" :min="0" :precision="2" size="small" style="width:120px" />
              <el-button size="small" type="primary" @click="saveTarget(row)">确定</el-button>
              <el-button size="small" @click="editingId = null">取消</el-button>
            </template>
            <template v-else>
              <span>{{ row.target_price ? '¥' + row.target_price.toFixed(2) : '-' }}</span>
              <el-button size="small" style="margin-left:8px" @click="editTarget(row)">设置</el-button>
            </template>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push('/history/' + row.id)">走势</el-button>
            <el-popconfirm title="确定移除？" @confirm="store.removeProduct(row.id)">
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
import { ref } from "vue";
import { useProductStore } from "../stores/products";

const store = useProductStore();
const editingId = ref(null);
const editingTarget = ref(0);

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
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
