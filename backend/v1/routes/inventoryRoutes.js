// routes/inventoryRoutes.js
import express from "express";

import {
  getAllProducts,
  getProductById,
  createProduct,
  updateProduct,
  deleteProduct,
  getInventoryStats,
} from "../controllers/inventoryController.js";

const router = express.Router();

router.get("/stats", getInventoryStats);

router
  .route("/")
  .get(getAllProducts)
  .post(createProduct);

router
  .route("/:id")
  .get(getProductById)
  .put(updateProduct)
  .delete(deleteProduct);

export default router;