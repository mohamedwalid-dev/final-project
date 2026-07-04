import mongoose from "mongoose";
import { VALID_USER_DEPARTMENTS, VALID_USER_ROLES } from "./User.js";
import { TICKET_PRIORITIES } from "./Ticket.js";

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

const internalMessageSchema = new mongoose.Schema(
  {
    senderId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "users",
    },
    senderRole: {
      type: String,
      enum: VALID_USER_ROLES,
      required: true,
    },
    senderDepartment: {
      type: String,
      enum: VALID_USER_DEPARTMENTS,
      required: true,
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
    isInternalNote: {
      type: Boolean,
      default: true,
    },
    attachments: {
      type: [attachmentSchema],
      default: [],
    },
  },
  { timestamps: true }
);

const chatSchema = new mongoose.Schema(
  {
    ticketId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Ticket",
      required: true,
      index: true,
    },
    chatType: {
      type: String,
      enum: ["internal_department"],
      default: "internal_department",
      required: true,
    },
    title: {
      type: String,
      required: true,
      trim: true,
    },
    requestedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "users",
    },
    requestedDepartment: {
      type: String,
      enum: VALID_USER_DEPARTMENTS,
      required: true,
    },
    requestedRole: {
      type: String,
      enum: VALID_USER_ROLES,
    },
    participants: {
      type: [
        {
          type: mongoose.Schema.Types.ObjectId,
          ref: "users",
        },
      ],
      default: [],
    },
    status: {
      type: String,
      enum: ["active", "closed"],
      default: "active",
    },
    priority: {
      type: String,
      enum: TICKET_PRIORITIES,
      default: "medium",
    },
    summary: {
      type: String,
      default: "",
      trim: true,
    },
    messages: {
      type: [internalMessageSchema],
      default: [],
    },
  },
  { timestamps: true }
);

const Chat = mongoose.model("Chat", chatSchema);

export default Chat;
