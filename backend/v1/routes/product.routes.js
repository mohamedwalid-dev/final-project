// routes/newProduct.routes.js

import express from "express";

import {
  createNewProduct,
  getAllNewProducts,
  getNewProductById,
  updateNewProduct,
  deleteNewProduct
} from "../controllers/product.controller.js";

import {
  createNewProductValidator,
  updateNewProductValidator,
  getNewProductByIdValidator,
  deleteNewProductValidator
} from "../middleware/product.validator.js";

import { validateRequest } from "../middleware/product.middleware.js";

const router = express.Router();

router.post(
  "/",
  createNewProductValidator,
  validateRequest,
  createNewProduct
);

router.get("/", getAllNewProducts);

router.get(
  "/:id",
  getNewProductByIdValidator,
  validateRequest,
  getNewProductById
);

router.put(
  "/:id",
  updateNewProductValidator,
  validateRequest,
  updateNewProduct
);

router.patch(
  "/:id",
  updateNewProductValidator,
  validateRequest,
  updateNewProduct
);

router.delete(
  "/:id",
  deleteNewProductValidator,
  validateRequest,
  deleteNewProduct
);

export default router;
