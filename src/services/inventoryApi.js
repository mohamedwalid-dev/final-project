const API_URL = "http://localhost:5005/v1/inventory";

const getAuthHeaders = () => {
  const token = localStorage.getItem("token");

  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
};

const parseResponse = async (response) => {
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      payload.message || payload.error || "Inventory request failed"
    );
  }

  return payload;
};

const request = async (path = "", options = {}) => {
  const response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    ...options,
    headers: {
      ...getAuthHeaders(),
      ...(options.headers || {}),
    },
  });

  return parseResponse(response);
};

export const getInventoryProducts = async () => {
  const payload = await request();
  return payload.data;
};

export const getInventoryStats = async () => {
  const payload = await request("/stats");
  return payload.data;
};

export const getInventoryProductById = async (productId) => {
  const payload = await request(`/${productId}`);
  return payload.data;
};

export const createInventoryProduct = async (productData) => {
  const payload = await request("", {
    method: "POST",
    body: JSON.stringify(productData),
  });

  return payload.data;
};

export const updateInventoryProduct = async (productId, productData) => {
  const response = await fetch(`${API_URL}/${productId}`, {
    method: "PUT",
    credentials: "include",
    headers: getAuthHeaders(),
    body: JSON.stringify(productData),
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      payload.message || payload.error || "Failed to update product."
    );
  }

  return payload.product || payload.data || payload;
};

export const deleteInventoryProduct = async (productId) => {
  return request(`/${productId}`, {
    method: "DELETE",
  });
};

export const importInventoryProductsCsv = async (products) => {
  return request("/products/import-csv", {
    method: "POST",
    body: JSON.stringify({ products }),
  });
};
