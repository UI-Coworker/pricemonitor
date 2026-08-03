<template>
  <el-container>
    <el-header class="app-header">
      <div class="header-left">
        <span class="app-title">📊 PriceMonitor</span>
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
.app-title {
  font-size: 20px;
  font-weight: bold;
  color: #303133;
}
</style>
