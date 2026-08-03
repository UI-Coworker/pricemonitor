import { createRouter, createWebHistory } from "vue-router";
import * as api from "../api";
import Login from "../views/Login.vue";
import Products from "../views/Products.vue";
import History from "../views/History.vue";

const routes = [
  { path: "/", redirect: "/login" },
  { path: "/login", component: Login },
  { path: "/products", component: Products },
  { path: "/history/:id", component: History, props: true },
];

const router = createRouter({ history: createWebHistory(), routes });

router.beforeEach(async (to, _from, next) => {
  if (to.path === "/login") return next();
  try {
    const r = await api.loginStatus();
    if (r.data.logged_in) return next();
  } catch {}
  next("/login");
});

export default router;
