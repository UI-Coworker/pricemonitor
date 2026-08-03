import axios from "axios";

const api = axios.create({ baseURL: "/api" });

export function loginStart() {
  return api.post("/login/start");
}

export function loginStatus() {
  return api.get("/login/status");
}

export function getProducts() {
  return api.get("/products");
}

export function getProduct(id) {
  return api.get(`/products/${id}`);
}

export function setTarget(id, target) {
  return api.put(`/products/${id}/target`, { target });
}

export function deleteProduct(id) {
  return api.delete(`/products/${id}`);
}

export function syncCart() {
  return api.post("/sync");
}

export function checkPrices() {
  return api.post("/check");
}

export function getHistory(id, limit = 30) {
  return api.get(`/products/${id}/history`, { params: { limit } });
}

export function getConfig() {
  return api.get("/config");
}

export function updateConfig(data) {
  return api.put("/config", data);
}

export function watchStart() {
  return api.post("/watch/start");
}

export function watchStop() {
  return api.post("/watch/stop");
}

export function watchStatus() {
  return api.get("/watch/status");
}

export function logout() {
  return api.post("/logout");
}
