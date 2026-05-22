import mongoose from "mongoose";

const chatMessageSchema = new mongoose.Schema(
  {
    senderType: {
      type: String,
      enum: ["customer", "agent", "system"],
      required: true,
      default: "customer",
    },

    senderName: {
      type: String,
      default: "",
      trim: true,
    },

    message: {
      type: String,
      required: true,
      trim: true,
    },

    isInternalNote: {
      type: Boolean,
      default: false,
    },

    attachments: [
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
    ],
  },
  { timestamps: true }
);

const chatSchema = new mongoose.Schema(
  {
    ticketId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Ticket",
      required: true,
    },

    ticketCode: {
      type: String,
      required: true,
      trim: true,
    },

    customerName: {
      type: String,
      required: true,
      trim: true,
    },

    customerEmail: {
      type: String,
      required: true,
      trim: true,
      lowercase: true,
    },

    assignedAgent: {
      type: String,
      default: "Unassigned",
      trim: true,
    },

    status: {
      type: String,
      enum: ["active", "closed"],
      default: "active",
    },

    messages: [chatMessageSchema],
  },
  { timestamps: true }
);

const Chat = mongoose.model("Chat", chatSchema);

export default Chat;