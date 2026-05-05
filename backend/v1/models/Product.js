import mongoose from "mongoose";

const NewProductSchema = new mongoose.Schema({
  productName: {
    type: String,
    required: true,
    trim: true
  },

  sku: {
    type: String,
    required: true,
    unique: true,
    trim: true,
    uppercase: true
  },

  category: {
    type: String,
    required: true,
    trim: true
  },

  location: {
    type: String,
    required: true,
    trim: true
  },

  initialStatus: {
    type: String,
    required: true,
    enum: ["In Stock", "Out of Stock", "Pending"]
  },

  unitCount: {
    type: Number,
    required: true,
    min: 0
  },

  lowStockThreshold: {
    type: Number,
    required: true,
    min: 0
  }

}, {
  timestamps: true
});

// Unique index for SKU
// NewProductSchema.index({ sku: 1 }, { unique: true });

// Optional custom validation: unitCount >= lowStockThreshold
NewProductSchema.pre("save", function (next) {
  if (this.unitCount < this.lowStockThreshold) {
    console.warn("Warning: unitCount is below lowStockThreshold");
    // You can block save instead by using:
    // return next(new Error("unitCount cannot be less than lowStockThreshold"));
  }
//   next();
});

export default mongoose.model("Product", NewProductSchema)