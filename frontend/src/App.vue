<template>
  <el-container v-if="store.loggedIn">
    <el-header class="app-header">
      <span class="app-title">📊 PriceMonitor</span>
      <el-button text @click="doLogout">退出登录</el-button>
    </el-header>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
  <div v-else>
    <router-view />
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useProductStore } from "./stores/products";

const store = useProductStore();
const router = useRouter();

async function doLogout() {
  await store.logout();
  router.push("/login");
}

onMounted(async () => {
  await store.checkLogin();
});
</script>

<style>
body { margin: 0; background: #f5f7fa; }
.app-header {
  background: #fff; border-bottom: 1px solid #e4e7ed;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 60px;
}
.app-title { font-size: 20px; font-weight: bold; color: #303133; }
</style>
