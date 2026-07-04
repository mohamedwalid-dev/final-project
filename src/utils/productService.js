// ─── utils/productService.js ──────────────────────────────────────────────────
import { http } from "../api/client";
import { ENDPOINTS } from "../api/endpoints";

const productService = {
  // Fetch all products
  fetchProducts: async (signal) => {
    try {
      const result = await http.get(ENDPOINTS.PRODUCTS.LIST, { signal });
      if (result.error) return { data: null, error: result.error };
      const products = Array.isArray(result.data?.data) ? result.data.data : [];
      return { data: products, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to fetch products" };
    }
  },

  // Create product
  createProduct: async (payload) => {
    try {
      const result = await http.post(ENDPOINTS.PRODUCTS.CREATE, payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to create product" };
    }
  },

  // Get product by ID
  getProduct: async (id) => {
    try {
      const result = await http.get(ENDPOINTS.PRODUCTS.DETAIL(id));
      if (result.error) return { data: null, error: result.error };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to fetch product" };
    }
  },

  // Update product
  updateProduct: async (id, payload) => {
    try {
      const result = await http.patch(ENDPOINTS.PRODUCTS.UPDATE(id), payload);
      if (result.error) return { data: null, error: result.error, errorData: result.errorData };
      return { data: result.data?.data, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to update product" };
    }
  },

  // Delete product
  deleteProduct: async (id) => {
    try {
      const result = await http.delete(ENDPOINTS.PRODUCTS.DELETE(id));
      if (result.error) return { data: null, error: result.error };
      return { data: true, error: null };
    } catch (err) {
      return { data: null, error: err.message || "Failed to delete product" };
    }
  },
};

export default productService;
