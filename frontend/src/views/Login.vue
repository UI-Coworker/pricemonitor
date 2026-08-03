<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>扫码登录京东</h2>
      <div v-if="autoChecking" style="padding: 40px">
        <p>正在检查登录状态…</p>
      </div>
      <div v-else-if="polling">
        <p style="padding: 20px">请在弹出的浏览器窗口中用京东 App 扫码</p>
        <el-button type="warning" @click="cancelLogin">取消</el-button>
      </div>
      <div v-else>
        <el-button type="primary" size="large" @click="startLogin">登录</el-button>
        <p v-if="error" class="error">{{ error }}</p>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useProductStore } from "../stores/products";

const store = useProductStore();
const router = useRouter();
const polling = ref(false);
const error = ref("");
const autoChecking = ref(true);

onMounted(async () => {
  await store.checkLogin();
  if (store.loggedIn) {
    router.push("/products");
    return;
  }
  autoChecking.value = false;
});

async function startLogin() {
  error.value = "";
  polling.value = true;
  try {
    const r = await store.initLogin();
    if (r.data.logged_in) {
      store.loggedIn = true;
      router.push("/products");
      return;
    }
    pollLogin();
  } catch (e) {
    error.value = "启动失败: " + (e.response?.data?.detail || e.message);
    polling.value = false;
  }
}

async function pollLogin() {
  for (let i = 0; i < 180; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    if (!polling.value) return;
    try {
      const data = await store.pollLogin();
      if (data.logged_in) {
        store.loggedIn = true;
        router.push("/products");
        return;
      }
    } catch {
      // retry
    }
  }
  error.value = "登录超时，请重试";
  polling.value = false;
}

function cancelLogin() {
  polling.value = false;
  error.value = "";
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
.error {
  color: #f56c6c;
  margin-top: 8px;
}
</style>
