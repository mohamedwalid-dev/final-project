import mongoose from "mongoose";

const lineItemSchema = new mongoose.Schema(
  {
    description: {
      type: String,
      required: true,
      trim: true,
    },
    quantity: {
      type: Number,
      required: true,
      min: 1,
    },
    unitPrice: {
      type: Number,
      required: true,
      min: 0,
    },
    total: {
      type: Number,
      required: true,
      min: 0,
    },
  },
  { _id: false }
);

const invoiceSchema = new mongoose.Schema(
  {
    status: {
      type: String,
      enum: ["Paid", "Pending", "Overdue"],
      default: "Pending",
      required: true,
    },

    clientInformation: {
      customerName: {
        type: String,
        required: true,
        trim: true,
      },
      billingEmail: {
        type: String,
        required: true,
        trim: true,
        lowercase: true,
        match: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
      },
      billingAddress: {
        type: String,
        required: true,
        trim: true,
      },
    },

    invoiceTimeline: {
      issueDate: {
        type: Date,
        required: true,
      },
      dueDate: {
        type: Date,
        required: true,
      },
      poNumber: {
        type: String,
        default: null,
        trim: true,
      },
      currency: {
        type: String,
        required: true,
        uppercase: true,
        trim: true,
        default: "USD",
        enum: ["USD", "EGP", "SAR"],
      },
    },

    lineItems: {
      type: [lineItemSchema],
      required: true,
      validate: {
        validator: function (items) {
          return Array.isArray(items) && items.length > 0;
        },
        message: "At least one line item is required",
      },
    },

    taxConfiguration: {
      customTaxRate: {
        type: Number,
        min: 0,
        max: 100,
        default: 0,
      },
    },

    discountAndNotes: {
      discountAmountUSD: {
        type: Number,
        min: 0,
        default: 0,
      },
      internalNotes: {
        type: String,
        default: "",
        trim: true,
      },
    },
  },
  {
    timestamps: true,
  }
);

export default mongoose.model("Invoice", invoiceSchema);