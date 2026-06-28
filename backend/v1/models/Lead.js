import mongoose from "mongoose";

const leadSchema = new mongoose.Schema(
  {
    companyName: {
      type: String,
      trim: true,
    },
    clientName: {
      type: String,
      trim: true,
      required: true,
    },
    email: {
      type: String,
      trim: true,
      required: true,
      lowercase: true,
    },
    phone: {
      type: String,
      trim: true,
    },
    address: {
      type: String,
      trim: true,
    },
    dealValue: {
      type: Number,
      required: true,
      min: 0,
      default: 0,
    },
    priority: {
      type: String,
      enum: ["Low", "Medium", "High"],
      default: "Medium",
    },
    stage: {
      type: String,
      enum: ["New", "Contacted", "Proposal", "Negotiation", "Closed", "Closed Won", "Closed Lost"],
      default: "New",
    },
    status: {
      type: String,
      enum: ["Open", "Won", "Lost"],
      default: "Open",
    },
    notes: {
      type: String,
      trim: true,
    },
  },
  {
    timestamps: true,
  }
);

export default mongoose.model("Lead", leadSchema);