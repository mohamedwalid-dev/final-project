// controllers/inventoryController.js
import Inventory, { getInventoryStockMeta } from "../models/inventoryModel.js";

const getStringValue = (value) => (value == null ? "" : String(value).trim());

const getRequiredNumber = (value, rowNumber, label) => {
  if (value === "" || value == null) {
    throw new Error(`Row ${rowNumber}: ${label} must be a valid number.`);
  }

  const numberValue = Number(value);

  if (!Number.isFinite(numberValue) || numberValue < 0) {
    throw new Error(`Row ${rowNumber}: ${label} must be a valid number.`);
  }

  return numberValue;
};

const isDuplicateKeyError = (error) =>
  error?.code === 11000 ||
  error?.writeErrors?.some((writeError) => writeError?.code === 11000);

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

// IMPORT products from CSV payload
export const importInventoryProductsCsv = async (req, res) => {
  try {
    const { products } = req.body;

    if (!Array.isArray(products) || products.length === 0) {
      return res.status(400).json({
        success: false,
        message: "Products array is required.",
      });
    }

    const allowedCategories = Inventory.schema.path("category").enumValues;
    const allowedLocations = Inventory.schema.path("location").enumValues;
    const seenSkus = new Set();

    const normalizedProducts = products.map((product, index) => {
      const rowNumber = index + 1;
      const name = getStringValue(product.name);
      const category = getStringValue(product.category);
      const sku = getStringValue(product.sku).toUpperCase();
      const location = getStringValue(product.location);

      if (!name) {
        throw new Error(`Row ${rowNumber}: Product name is required.`);
      }

      if (!category) {
        throw new Error(`Row ${rowNumber}: Category is required.`);
      }

      if (!sku) {
        throw new Error(`Row ${rowNumber}: SKU is required.`);
      }

      if (!location) {
        throw new Error(`Row ${rowNumber}: Location is required.`);
      }

      if (!allowedCategories.includes(category)) {
        throw new Error(
          `Row ${rowNumber}: Category must be one of ${allowedCategories.join(
            ", "
          )}.`
        );
      }

      if (!allowedLocations.includes(location)) {
        throw new Error(
          `Row ${rowNumber}: Location must be one of ${allowedLocations.join(
            ", "
          )}.`
        );
      }

      const price = getRequiredNumber(product.price, rowNumber, "Price");
      const units = getRequiredNumber(product.units, rowNumber, "Units");
      const threshold = getRequiredNumber(
        product.threshold,
        rowNumber,
        "Threshold"
      );

      if (seenSkus.has(sku)) {
        const error = new Error(
          `Row ${rowNumber}: Duplicate SKU "${sku}" in import payload.`
        );
        error.statusCode = 409;
        throw error;
      }

      seenSkus.add(sku);

      const stockMeta = getInventoryStockMeta(units, threshold);

      return {
        name,
        category,
        sku,
        location,
        price,
        units,
        threshold,
        stockPct: stockMeta.stockPct,
        status: stockMeta.status,
      };
    });

    const skus = normalizedProducts.map((product) => product.sku);
    const existingProducts = await Inventory.find({ sku: { $in: skus } })
      .select("sku")
      .lean();

    if (existingProducts.length > 0) {
      return res.status(409).json({
        success: false,
        message: `One or more products have duplicate SKU values: ${existingProducts
          .map((product) => product.sku)
          .join(", ")}.`,
      });
    }

    const createdProducts = await Inventory.insertMany(normalizedProducts);

    return res.status(201).json({
      success: true,
      message: `${createdProducts.length} products imported successfully.`,
      importedCount: createdProducts.length,
      products: createdProducts,
      data: createdProducts,
    });
  } catch (error) {
    console.error("Import inventory products CSV error:", error);

    if (isDuplicateKeyError(error)) {
      return res.status(409).json({
        success: false,
        message: "One or more products have duplicate SKU values.",
        error: error.message,
      });
    }

    return res.status(error.statusCode || 400).json({
      success: false,
      message: error.message || "Failed to import inventory products.",
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

    const allowedUpdates = [
      "name",
      "category",
      "sku",
      "location",
      "price",
      "units",
      "threshold",
    ];

    allowedUpdates.forEach((field) => {
      if (req.body[field] !== undefined) {
        product[field] = req.body[field];
      }
    });

    product.price = Number(product.price);
    product.units = Number(product.units);
    product.threshold = Number(product.threshold);

    const stockMeta = getInventoryStockMeta(product.units, product.threshold);
    product.stockPct = stockMeta.stockPct;
    product.status = stockMeta.status;

    await product.save();

    res.status(200).json({
      success: true,
      message: "Product updated successfully",
      product,
      data: product,
    });
  } catch (error) {
    console.error("Update inventory product error:", error);

    if (isDuplicateKeyError(error)) {
      return res.status(409).json({
        success: false,
        message: "SKU already exists. Please use a different SKU.",
      });
    }

    res.status(400).json({
      success: false,
      message: error.message || "Failed to update product.",
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

    const totalSum = products.reduce(
      (sum, item) => sum + Number(item.price || 0),
      0
    );

    res.status(200).json({
      success: true,
      data: {
        totalProducts,
        totalUnits,
        lowStockItems,
        outOfStockItems,
        averageStock,
        totalSum,
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
