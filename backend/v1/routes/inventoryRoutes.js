// routes/inventoryRoutes.js
import express from "express";
import {
  createProductValidator,
  updateProductValidator,
} from "../middleware/product.validator.js";
import { validateRequest } from "../middleware/product.middleware.js";

import {
  getAllProducts,
  getProductById,
  createProduct,
  importInventoryProductsCsv,
  updateProduct,
  deleteProduct,
  getInventoryStats,
} from "../controllers/inventoryController.js";

const router = express.Router();

router.get("/stats", getInventoryStats);

router
  .route("/")
  .get(getAllProducts)
  .post(createProductValidator, validateRequest, createProduct);

router.post("/products/import-csv", importInventoryProductsCsv);

router
  .route("/:id")
  .get(getProductById)
  .put(updateProductValidator, validateRequest, updateProduct)
  .delete(deleteProduct);

export default router;
