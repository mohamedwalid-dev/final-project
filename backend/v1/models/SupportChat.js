import mongoose from "mongoose";

const supportChatMessageSchema = new mongoose.Schema(
  {
    senderId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "users",
    },
    senderRole: {
      type: String,
      trim: true,
    },
    senderName: {
      type: String,
      trim: true,
    },
    senderEmail: {
      type: String,
      trim: true,
      lowercase: true,
    },
    text: {
      type: String,
      required: true,
      trim: true,
    },
    messageType: {
      type: String,
      enum: ["text", "system"],
      default: "text",
    },
    readByUser: {
      type: Boolean,
      default: false,
    },
    readBySupport: {
      type: Boolean,
      default: false,
    },
    createdAt: {
      type: Date,
      default: Date.now,
    },
  },
  { _id: true }
);

const supportChatSchema = new mongoose.Schema(
  {
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "users",
      required: true,
      unique: true,
      index: true,
    },
    userName: {
      type: String,
      trim: true,
    },
    userEmail: {
      type: String,
      trim: true,
      lowercase: true,
    },
    assignedSupportAgent: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "users",
      default: null,
    },
    status: {
      type: String,
      enum: ["open", "pending", "closed"],
      default: "open",
    },
    lastMessage: {
      type: String,
      default: "",
      trim: true,
    },
    lastMessageAt: {
      type: Date,
      default: Date.now,
    },
    unreadByUser: {
      type: Number,
      default: 0,
      min: 0,
    },
    unreadBySupport: {
      type: Number,
      default: 0,
      min: 0,
    },
    messages: {
      type: [supportChatMessageSchema],
      default: [],
    },
  },
  { timestamps: true }
);

const SupportChat = mongoose.model("SupportChat", supportChatSchema);

export default SupportChat;
