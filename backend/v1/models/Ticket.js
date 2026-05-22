import mongoose from "mongoose";
import { VALID_USER_DEPARTMENTS } from "./User.js";

export const TICKET_PRIORITIES = ["urgent", "high", "medium", "low"];
export const TICKET_STATUSES = ["open", "pending", "resolved", "closed"];
export const TICKET_CATEGORIES = [
  "invoice",
  "payment",
  "hr",
  "technical",
  "sales",
  "general",
];

const attachmentSchema = new mongoose.Schema(
  {
    fileName: {
      type: String,
      trim: true,
    },
    fileUrl: {
      type: String,
      trim: true,
    },
    fileType: {
      type: String,
      trim: true,
    },
  },
  { _id: false }
);

const ticketMessageSchema = new mongoose.Schema(
  {
    senderId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "users",
    },
    senderType: {
      type: String,
      enum: ["client", "support", "system"],
      required: true,
      default: "client",
    },
    senderName: {
      type: String,
      required: true,
      trim: true,
    },
    text: {
      type: String,
      required: true,
      trim: true,
    },
    attachments: {
      type: [attachmentSchema],
      default: [],
    },
  },
  { timestamps: true }
);

const ticketSchema = new mongoose.Schema(
  {
    ticketCode: {
      type: String,
      unique: true,
      required: true,
      trim: true,
      index: true,
    },
    clientId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "users",
    },
    clientName: {
      type: String,
      required: true,
      trim: true,
    },
    clientEmail: {
      type: String,
      required: true,
      trim: true,
      lowercase: true,
    },
    subject: {
      type: String,
      required: true,
      trim: true,
    },
    description: {
      type: String,
      required: true,
      trim: true,
    },
    priority: {
      type: String,
      enum: TICKET_PRIORITIES,
      default: "medium",
    },
    status: {
      type: String,
      enum: TICKET_STATUSES,
      default: "open",
    },
    category: {
      type: String,
      enum: TICKET_CATEGORIES,
      default: "general",
    },
    assignedSupportAgent: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "users",
    },
    relatedDepartment: {
      type: String,
      enum: VALID_USER_DEPARTMENTS,
      default: "support",
    },
    preview: {
      type: String,
      default: "",
      trim: true,
    },
    messages: {
      type: [ticketMessageSchema],
      default: [],
    },
  },
  { timestamps: true }
);

const Ticket = mongoose.model("Ticket", ticketSchema);

export default Ticket;
