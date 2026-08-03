<template>
  <el-container>
    <el-header class="app-header">
      <div class="header-left">
        <h2 @click="$router.push('/dashboard')" style="cursor:pointer">📊 PriceMonitor</h2>
      </div>
      <div class="header-right">
        <el-menu mode="horizontal" :default-active="$route.path" router>
          <el-menu-item index="/dashboard">仪表盘</el-menu-item>
          <el-menu-item index="/products">商品管理</el-menu-item>
        </el-menu>
      </div>
    </el-header>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useProductStore } from "./stores/products";

const store = useProductStore();
const router = useRouter();

onMounted(async () => {
  await store.checkLogin();
  if (!store.loggedIn) {
    router.push("/login");
  }
});
</script>

<style>
body {
  margin: 0;
  background: #f5f7fa;
}
.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 60px;
}
.app-header h2 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}
</style>
