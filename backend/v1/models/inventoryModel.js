// models/inventoryModel.js
import mongoose from "mongoose";

export function getInventoryStockMeta(units, threshold) {
  const safeUnits = Number(units || 0);
  const safeThreshold = Number(threshold || 0);

  const stockPct =
    safeThreshold > 0
      ? Math.min(100, Math.round((safeUnits / (safeThreshold * 2)) * 100))
      : 100;

  let status = "Healthy";

  if (safeUnits === 0) {
    status = "Out";
  } else if (safeUnits <= safeThreshold) {
    status = "Critical";
  } else if (stockPct < 50) {
    status = "Warning";
  }

  return { stockPct, status };
}

const inventorySchema = new mongoose.Schema(
  {
    name: {
      type: String,
      required: [true, "Product name is required"],
      trim: true,
    },

    category: {
      type: String,
      required: [true, "Category is required"],
      trim: true,
      enum: ["Electronics", "Consumables", "Hardware", "Software", "Components"],
      default: "Electronics",
    },

    sku: {
      type: String,
      required: [true, "SKU is required"],
      unique: true,
      trim: true,
      uppercase: true,
    },

    location: {
      type: String,
      required: [true, "Location is required"],
      trim: true,
      enum: [
        "Warehouse A-12",
        "Warehouse A-10",
        "Warehouse B-04",
        "Central Hub",
        "Secure Vault",
      ],
      default: "Warehouse A-12",
    },

    price: {
      type: Number,
      required: [true, "Product price is required"],
      min: [0, "Product price cannot be negative"],
      default: 0,
    },

    units: {
      type: Number,
      required: [true, "Units are required"],
      min: [0, "Units cannot be negative"],
      default: 0,
    },

    threshold: {
      type: Number,
      required: [true, "Threshold is required"],
      min: [0, "Threshold cannot be negative"],
      default: 0,
    },

    stockPct: {
      type: Number,
      min: 0,
      max: 100,
      default: 0,
    },

    status: {
      type: String,
      enum: ["Healthy", "Warning", "Critical", "Low", "Out"],
      default: "Healthy",
    },
  },
  {
    timestamps: true,
  }
);

// Auto-calculate stock percentage and status before save
inventorySchema.pre("save", function () {
  const stockMeta = getInventoryStockMeta(this.units, this.threshold);
  this.stockPct = stockMeta.stockPct;
  this.status = stockMeta.status;
});

const Inventory = mongoose.model("Inventory", inventorySchema);

export default Inventory;
