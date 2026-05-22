import mongoose from "mongoose";

const messageSchema = new mongoose.Schema(
  {
    from: {
      type: String,
      enum: ["customer", "agent", "system"],
      required: true,
      default: "customer",
    },

    text: {
      type: String,
      required: true,
      trim: true,
    },

    time: {
      type: String,
      default: () =>
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
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
    },

    name: {
      type: String,
      required: true,
      trim: true,
    },

    email: {
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

    preview: {
      type: String,
      default: "",
    },

    priority: {
      type: String,
      enum: ["urgent", "high", "medium", "low"],
      default: "medium",
    },

    status: {
      type: String,
      enum: ["open", "pending", "resolved", "closed"],
      default: "open",
    },

    avatar: {
      type: String,
      default: "NA",
    },

    avatarColor: {
      type: String,
      default: "#4A6FDC",
    },

    location: {
      type: String,
      default: "Unknown",
    },

    lastSeen: {
      type: String,
      default: "Last active just now",
    },

    messages: [messageSchema],
  },
  { timestamps: true }
);

const Ticket = mongoose.model("Ticket", ticketSchema);

export default Ticket;