// controllers/inventoryController.js
import Inventory from "../models/inventoryModel.js";

// GET all products
export const getAllProducts = async (req, res) => {
  try {
    const { search, status, category, location } = req.query;

    const filter = {};

    if (search) {
      filter.$or = [
        { name: { $regex: search, $options: "i" } },
        { sku: { $regex: search, $options: "i" } },
        { location: { $regex: search, $options: "i" } },
      ];
    }

    if (status) {
      filter.status = status;
    }

    if (category) {
      filter.category = category;
    }

    if (location) {
      filter.location = location;
    }

    const products = await Inventory.find(filter).sort({ createdAt: -1 });

    res.status(200).json({
      success: true,
      count: products.length,
      data: products,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to fetch inventory products",
      error: error.message,
    });
  }
};

// GET single product
export const getProductById = async (req, res) => {
  try {
    const product = await Inventory.findById(req.params.id);

    if (!product) {
      return res.status(404).json({
        success: false,
        message: "Product not found",
      });
    }

    res.status(200).json({
      success: true,
      data: product,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to fetch product",
      error: error.message,
    });
  }
};

// CREATE product
export const createProduct = async (req, res) => {
  try {
    const { name, category, sku, location, price, units, threshold } = req.body;

    const existingProduct = await Inventory.findOne({ sku: sku?.toUpperCase() });

    if (existingProduct) {
      return res.status(400).json({
        success: false,
        message: "SKU already exists",
      });
    }

    const product = await Inventory.create({
      name,
      category,
      sku,
      location,
      price: Number(price),
      units,
      threshold,
    });

    res.status(201).json({
      success: true,
      message: "Product added successfully",
      data: product,
    });
  } catch (error) {
    res.status(400).json({
      success: false,
      message: "Failed to create product",
      error: error.message,
    });
  }
};

// UPDATE product
export const updateProduct = async (req, res) => {
  try {
    const product = await Inventory.findById(req.params.id);

    if (!product) {
      return res.status(404).json({
        success: false,
        message: "Product not found",
      });
    }

    const {
      name,
      category,
      sku,
      location,
      price,
      units,
      threshold,
    } = req.body;

    const allowedUpdates = {
      ...(name !== undefined && { name }),
      ...(category !== undefined && { category }),
      ...(sku !== undefined && { sku }),
      ...(location !== undefined && { location }),
      ...(price !== undefined && { price: Number(price) }),
      ...(units !== undefined && { units }),
      ...(threshold !== undefined && { threshold }),
    };

    Object.assign(product, allowedUpdates);

    await product.save();

    res.status(200).json({
      success: true,
      message: "Product updated successfully",
      data: product,
    });
  } catch (error) {
    res.status(400).json({
      success: false,
      message: "Failed to update product",
      error: error.message,
    });
  }
};

// DELETE product
export const deleteProduct = async (req, res) => {
  try {
    const product = await Inventory.findById(req.params.id);

    if (!product) {
      return res.status(404).json({
        success: false,
        message: "Product not found",
      });
    }

    await product.deleteOne();

    res.status(200).json({
      success: true,
      message: "Product deleted successfully",
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to delete product",
      error: error.message,
    });
  }
};

// GET inventory stats
export const getInventoryStats = async (req, res) => {
  try {
    const products = await Inventory.find();

    const totalProducts = products.length;
    const totalUnits = products.reduce((sum, item) => sum + item.units, 0);

    const lowStockItems = products.filter(
      (item) =>
        item.status === "Low" ||
        item.status === "Critical" ||
        item.status === "Warning"
    ).length;

    const outOfStockItems = products.filter(
      (item) => item.status === "Out"
    ).length;

    const averageStock =
      totalProducts > 0
        ? Math.round(
            products.reduce((sum, item) => sum + item.stockPct, 0) /
              totalProducts
          )
        : 0;

    res.status(200).json({
      success: true,
      data: {
        totalProducts,
        totalUnits,
        lowStockItems,
        outOfStockItems,
        averageStock,
      },
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to fetch inventory stats",
      error: error.message,
    });
  }
};