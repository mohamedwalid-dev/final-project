export const ENDPOINTS = {
  AUTH: {
    REGISTER: "/auth/register",
    LOGIN: "/auth/login",
    LOGOUT: "/auth/logout",
    ME: "/auth/me",
  },
  EMPLOYEES: {
    LIST: "/employees",
    CREATE: "/employees",
    DETAIL: (id) => `/employees/${id}`,
    UPDATE: (id) => `/employees/${id}`,
    DELETE: (id) => `/employees/${id}`,
  },
  PRODUCTS: {
    LIST: "/products",
    CREATE: "/products",
    DETAIL: (id) => `/products/${id}`,
    UPDATE: (id) => `/products/${id}`,
    DELETE: (id) => `/products/${id}`,
  },
  INVOICES: {
    LIST: "/invoices",
    CREATE: "/invoices",
    DETAIL: (id) => `/invoices/${id}`,
    UPDATE: (id) => `/invoices/${id}`,
    DELETE: (id) => `/invoices/${id}`,
  },
  LEADS: {
    LIST: "/leads",
    CREATE: "/leads",
    DETAIL: (id) => `/leads/${id}`,
    UPDATE: (id) => `/leads/${id}`,
    DELETE: (id) => `/leads/${id}`,
    PRODUCT_SUGGESTIONS: "/leads/products/suggestions",
    PRODUCTS: (id) => `/leads/${id}/products`,
    PRODUCT_DETAIL: (leadId, productId) => `/leads/${leadId}/products/${productId}`,
  },
};

