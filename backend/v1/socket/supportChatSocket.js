import jwt from "jsonwebtoken";
import mongoose from "mongoose";
import Blacklist from "../models/Black-List.js";
import SupportChat from "../models/SupportChat.js";
import User from "../models/User.js";
import { SECRET_ACCESS_TOKEN } from "../config/index.js";

const isSupportUser = (user) => ["support", "admin"].includes(user?.role);

const getUserId = (user) => user?._id || user?.id;

const canAccessChat = (chat, user) =>
  isSupportUser(user) || chat?.userId?.toString() === getUserId(user)?.toString();

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
  });
};

export default initializeSupportChatSocket;
