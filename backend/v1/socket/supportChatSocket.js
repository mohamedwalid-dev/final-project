import jwt from "jsonwebtoken";
import mongoose from "mongoose";
import Blacklist from "../models/Black-List.js";
import Chat from "../models/Chat.js";
import SupportChat from "../models/SupportChat.js";
import User from "../models/User.js";
import { SECRET_ACCESS_TOKEN } from "../config/index.js";

const isSupportUser = (user) => ["support", "admin"].includes(user?.role);

const getUserId = (user) => user?._id || user?.id;

const canAccessChat = (chat, user) =>
  isSupportUser(user) || chat?.userId?.toString() === getUserId(user)?.toString();

const hasMatchingId = (value, target) => {
  if (!value || !target) return false;
  return String(value?._id || value) === String(target);
};

const canAccessInternalChat = (chat, user) => {
  if (!chat || user?.role === "client") return false;
  if (isSupportUser(user)) return true;

  const userId = getUserId(user);
  const userDepartment = user?.department;
  const ticketDepartment = chat.ticketId?.relatedDepartment;

  return (
    chat.requestedDepartment === userDepartment ||
    ticketDepartment === userDepartment ||
    hasMatchingId(chat.requestedBy, userId) ||
    (chat.participants || []).some((participant) => hasMatchingId(participant, userId))
  );
};

export const initializeSupportChatSocket = (io) => {
  io.use(async (socket, next) => {
    try {
      const token = socket.handshake.auth?.token;

      if (!token) {
        return next(new Error("Not authenticated"));
      }

      const blacklistedToken = await Blacklist.findOne({ token });
      if (blacklistedToken) {
        return next(new Error("Session expired. Please login again."));
      }

      const decoded = jwt.verify(token, SECRET_ACCESS_TOKEN);
      const user = await User.findById(decoded?.id).select("-password");

      if (!user) {
        return next(new Error("Not authenticated"));
      }

      socket.user = user.toObject();
      return next();
    } catch {
      return next(new Error("Session expired. Please login again."));
    }
  });

  io.on("connection", (socket) => {
    const userId = getUserId(socket.user);
    console.log("Socket connected:", socket.id);

    socket.join(`user:${userId}`);

    if (isSupportUser(socket.user)) {
      socket.join("support");
    }

    socket.on("join_support_chat", async ({ chatId } = {}) => {
      try {
        if (!mongoose.isValidObjectId(chatId)) {
          socket.emit("support_chat_error", { message: "Invalid support chat id." });
          return;
        }

        const chat = await SupportChat.findById(chatId).select("userId");

        if (!chat || !canAccessChat(chat, socket.user)) {
          socket.emit("support_chat_error", {
            message: "You are not allowed to join this support chat.",
          });
          return;
        }

        socket.join(`support-chat:${chatId}`);
      } catch {
        socket.emit("support_chat_error", { message: "Unable to join support chat." });
      }
    });

    socket.on("leave_support_chat", ({ chatId } = {}) => {
      if (mongoose.isValidObjectId(chatId)) {
        socket.leave(`support-chat:${chatId}`);
      }
    });

    socket.on("joinInternalChat", async (chatId) => {
      try {
        const roomId = String(chatId || "");
        if (!mongoose.isValidObjectId(roomId)) {
          socket.emit("internal_chat_error", { message: "Invalid internal chat id." });
          return;
        }

        const chat = await Chat.findById(roomId)
          .select("ticketId requestedBy requestedDepartment participants")
          .populate({ path: "ticketId", select: "relatedDepartment" });

        if (!canAccessInternalChat(chat, socket.user)) {
          socket.emit("internal_chat_error", {
            message: "You are not allowed to join this internal chat.",
          });
          return;
        }

        socket.join(roomId);
        console.log("Joined room:", roomId);
        console.log(`Socket ${socket.id} joined internal chat room: ${roomId}`);
      } catch {
        socket.emit("internal_chat_error", { message: "Unable to join internal chat." });
      }
    });

    socket.on("leaveInternalChat", (chatId) => {
      const roomId = String(chatId || "");
      if (mongoose.isValidObjectId(roomId)) {
        socket.leave(roomId);
        console.log(`Socket ${socket.id} left internal chat room: ${roomId}`);
      }
    });

    socket.on("disconnect", () => {
      console.log("Socket disconnected:", socket.id);
    });
  });
};

export default initializeSupportChatSocket;
