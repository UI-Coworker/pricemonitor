<template>
  <el-container>
    <el-header class="app-header">
      <div class="header-left">
        <span class="app-title">📊 PriceMonitor</span>
      </div>
      <div class="header-right">
        <el-menu mode="horizontal" :default-active="$route.path" router>
          <el-menu-item index="/products">商品总览</el-menu-item>
        </el-menu>
        <el-button text style="margin-left: 16px" @click="doLogout">退出登录</el-button>
      </div>
    </el-header>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { useRouter } from "vue-router";
import { useProductStore } from "./stores/products";

const store = useProductStore();
const router = useRouter();

function doLogout() {
  store.logout();
  router.push("/login");
}
</script>

<style>
body { margin: 0; background: #f5f7fa; }
.app-header {
  background: #fff; border-bottom: 1px solid #e4e7ed;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 60px;
}
.app-title { font-size: 20px; font-weight: bold; color: #303133; }
.header-right { display: flex; align-items: center; }
</style>
