// models/inventoryModel.js
import mongoose from "mongoose";

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
inventorySchema.pre("save", function (next) {
  if (this.threshold > 0) {
    this.stockPct = Math.min(
      100,
      Math.round((this.units / (this.threshold * 2)) * 100)
    );
  } else {
    this.stockPct = 100;
  }

  if (this.units === 0) {
    this.status = "Out";
  } else if (this.units <= this.threshold) {
    this.status = "Critical";
  } else if (this.stockPct < 50) {
    this.status = "Warning";
  } else {
    this.status = "Healthy";
  }

});

const Inventory = mongoose.model("Inventory", inventorySchema);

export default Inventory;