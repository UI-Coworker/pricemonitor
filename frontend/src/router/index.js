import { createRouter, createWebHistory } from "vue-router";
import Login from "../views/Login.vue";
import Dashboard from "../views/Dashboard.vue";
import Products from "../views/Products.vue";
import History from "../views/History.vue";

const routes = [
  { path: "/", redirect: "/dashboard" },
  { path: "/login", component: Login },
  { path: "/dashboard", component: Dashboard },
  { path: "/products", component: Products },
  { path: "/history/:id", component: History, props: true },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});
