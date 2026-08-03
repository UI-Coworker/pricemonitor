<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>扫码登录京东</h2>
      <div v-if="qrImage" class="qr-section">
        <img :src="'data:image/png;base64,' + qrImage" alt="QR Code" class="qr-img" />
        <p>请用京东 App 扫描二维码</p>
        <el-button type="primary" :loading="polling" @click="startLogin">刷新二维码</el-button>
        <p v-if="error" class="error">{{ error }}</p>
      </div>
      <div v-else>
        <el-button type="primary" size="large" @click="startLogin">获取登录二维码</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useProductStore } from "../stores/products";

const store = useProductStore();
const router = useRouter();
const qrImage = ref("");
const polling = ref(false);
const error = ref("");

async function startLogin() {
  error.value = "";
  polling.value = true;
  try {
    const r = await store.initLogin();
    const data = r.data;
    if (data.logged_in) {
      store.loggedIn = true;
      router.push("/dashboard");
      return;
    }
    qrImage.value = data.message;
    pollLogin();
  } catch (e) {
    error.value = "获取二维码失败: " + (e.response?.data?.detail || e.message);
    polling.value = false;
  }
}

async function pollLogin() {
  for (let i = 0; i < 120; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    try {
      const data = await store.pollLogin();
      if (data.logged_in) {
        router.push("/dashboard");
        return;
      }
    } catch {
      // retry
    }
  }
  error.value = "登录超时，请刷新二维码重试";
  polling.value = false;
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
}
.login-card {
  width: 400px;
  text-align: center;
}
.qr-img {
  width: 240px;
  height: 240px;
  border: 1px solid #eee;
  margin: 16px 0;
}
.error {
  color: #f56c6c;
  margin-top: 8px;
}
</style>
