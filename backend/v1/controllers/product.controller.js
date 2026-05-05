// controllers/newProduct.controller.js

import NewProduct from "../models/Product.js";
import AppError from "../utils/AppError.js";
import { sendSuccess } from "../utils/response.js";

export const createNewProduct = async (req, res, next) => {
  try {
    const product = await NewProduct.create(req.body);

    return sendSuccess(res, product, "Product created successfully", 201);
  } catch (error) {
    return next(error);
  }
};

export const getAllNewProducts = async (req, res, next) => {
  try {
    const products = await NewProduct.find();

    return sendSuccess(res, products, "Products fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const getNewProductById = async (req, res, next) => {
  try {
    const product = await NewProduct.findById(req.params.id);

    if (!product) {
      throw new AppError("Product not found", 404);
    }

    return sendSuccess(res, product, "Product fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const updateNewProduct = async (req, res, next) => {
  try {
    const product = await NewProduct.findByIdAndUpdate(
      req.params.id,
      req.body,
      { new: true, runValidators: true }
    );

    if (!product) {
      throw new AppError("Product not found", 404);
    }

    return sendSuccess(res, product, "Product updated successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const deleteNewProduct = async (req, res, next) => {
  try {
    const product = await NewProduct.findByIdAndDelete(req.params.id);

    if (!product) {
      throw new AppError("Product not found", 404);
    }

    return sendSuccess(res, [], "Product deleted successfully", 200);
  } catch (error) {
    return next(error);
  }
};
