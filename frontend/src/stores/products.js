import { defineStore } from "pinia";
import * as api from "../api";

export const useProductStore = defineStore("products", {
  state: () => ({
    products: [],
    loading: false,
    loggedIn: false,
    checking: false,
  }),

  actions: {
    async checkLogin() {
      try {
        const r = await api.loginStatus();
        this.loggedIn = r.data.logged_in;
      } catch {
        this.loggedIn = false;
      }
    },

    async initLogin() {
      return api.loginStart();
    },

    async pollLogin() {
      const r = await api.loginStatus();
      this.loggedIn = r.data.logged_in;
      return r.data;
    },

    async loadProducts() {
      this.loading = true;
      try {
        const r = await api.getProducts();
        this.products = r.data;
      } finally {
        this.loading = false;
      }
    },

    async syncCart() {
      this.loading = true;
      try {
        const r = await api.syncCart();
        this.products = r.data.products;
        return r.data;
      } finally {
        this.loading = false;
      }
    },

    async checkPrices() {
      this.checking = true;
      try {
        const r = await api.checkPrices();
        this.products = r.data.products;
        return r.data;
      } finally {
        this.checking = false;
      }
    },

    async setTarget(id, target) {
      await api.setTarget(id, target);
      await this.loadProducts();
    },

    async removeProduct(id) {
      await api.deleteProduct(id);
      await this.loadProducts();
    },

    logout() {
      this.loggedIn = false;
      this.products = [];
    },
  },
});
