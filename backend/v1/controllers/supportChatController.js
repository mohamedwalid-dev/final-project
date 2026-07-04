import mongoose from "mongoose";
import SupportChat from "../models/SupportChat.js";

const supportChatPopulate = [
  { path: "userId", select: "name first_name last_name email role department isActive" },
  {
    path: "assignedSupportAgent",
    select: "name first_name last_name email role department isActive",
  },
];

const isSupportUser = (user) => ["support", "admin"].includes(user?.role);

const getUserId = (user) => user?._id || user?.id;

const getUserName = (user) =>
  user?.name ||
  [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim() ||
  user?.email ||
  "User";

const sendSuccessResponse = (
  res,
  data,
  message = "Operation completed successfully",
  statusCode = 200
) =>
  res.status(statusCode).json({
    status: "success",
    success: true,
    data,
    message,
  });

const sendErrorResponse = (res, message, statusCode = 400) =>
  res.status(statusCode).json({
    status: "failed",
    success: false,
    data: [],
    message,
  });

const ensureAuthenticated = (req, res) => {
  if (!req.user || !getUserId(req.user)) {
    sendErrorResponse(res, "Not authenticated", 401);
    return false;
  }

  return true;
};

const ensureSupportAccess = (req, res) => {
  if (!isSupportUser(req.user)) {
    sendErrorResponse(res, "You are not allowed to access support chat inbox.", 403);
    return false;
  }

  return true;
};

const findOrCreateUserChatDocument = async (user) => {
  const userId = getUserId(user);
  const userName = getUserName(user);
  const userEmail = user?.email || "";

  let chat = await SupportChat.findOne({ userId });

  if (!chat) {
    chat = await SupportChat.create({
      userId,
      userName,
      userEmail,
      status: "open",
      lastMessage: "",
      lastMessageAt: new Date(),
      messages: [],
    });
  } else {
    let shouldSave = false;

    if (userName && chat.userName !== userName) {
      chat.userName = userName;
      shouldSave = true;
    }

    if (userEmail && chat.userEmail !== userEmail) {
      chat.userEmail = userEmail;
      shouldSave = true;
    }

    if (shouldSave) await chat.save();
  }

  return chat;
};

const findOrCreateUserChat = async (user) => {
  const chat = await findOrCreateUserChatDocument(user);
  return SupportChat.findById(chat._id).populate(supportChatPopulate);
};

const findChatDocumentById = async (chatId) => {
  if (!mongoose.isValidObjectId(chatId)) return null;
  return SupportChat.findById(chatId);
};

const isChatOwner = (chat, user) =>
  chat?.userId?._id?.toString() === getUserId(user)?.toString() ||
  chat?.userId?.toString() === getUserId(user)?.toString();

const canAccessChat = (chat, user) => isSupportUser(user) || isChatOwner(chat, user);

const toPayload = (document) => (document?.toObject ? document.toObject() : document);

const getChatUserId = (chat) => chat?.userId?._id || chat?.userId;

const getChatRoom = (chat) => `support-chat:${chat?._id}`;

const getUserRoom = (userId) => `user:${userId}`;

const getLatestMessage = (chat) => {
  const messages = chat?.messages || [];
  return toPayload(messages[messages.length - 1]);
};

const emitToRooms = (io, rooms, event, payload) => {
  if (!io) return;

  const uniqueRooms = [...new Set(rooms.filter(Boolean).map(String))];
  if (!uniqueRooms.length) return;

  uniqueRooms.reduce((target, room) => target.to(room), io).emit(event, payload);
};

const emitChatUpdated = (req, chat, rooms) => {
  emitToRooms(req.app.get("io"), rooms, "support_chat_updated", {
    chat: toPayload(chat),
  });
};

const emitMessageReceived = (req, chat, message, rooms) => {
  emitToRooms(req.app.get("io"), rooms, "support_message_received", {
    chatId: chat?._id?.toString(),
    message: toPayload(message),
    chat: toPayload(chat),
  });
};

const appendMessage = (chat, user, text, options = {}) => {
  const senderIsSupport = isSupportUser(user);

  chat.messages.push({
    senderId: getUserId(user),
    senderRole: user?.role || "client",
    senderName: getUserName(user),
    senderEmail: user?.email || "",
    text,
    messageType: options.messageType || "text",
    readByUser: !senderIsSupport,
    readBySupport: senderIsSupport,
  });

  chat.lastMessage = text;
  chat.lastMessageAt = new Date();

  if (senderIsSupport) {
    chat.unreadByUser += 1;
    chat.unreadBySupport = Math.max(0, chat.unreadBySupport);
  } else {
    chat.unreadBySupport += 1;
    chat.unreadByUser = Math.max(0, chat.unreadByUser);
  }

  if (chat.status === "closed") chat.status = "open";
};

export const getMySupportChat = async (req, res) => {
  try {
    if (!ensureAuthenticated(req, res)) return;

    const chat = await findOrCreateUserChat(req.user);
    const populatedChat = await SupportChat.findById(chat._id).populate(supportChatPopulate);
    return sendSuccessResponse(res, populatedChat, "Support chat fetched successfully");
  } catch (error) {
    return sendErrorResponse(res, error.message || "Failed to fetch support chat", 500);
  }
};

export const sendMySupportMessage = async (req, res) => {
  try {
    if (!ensureAuthenticated(req, res)) return;

    const text = req.body?.text?.trim();
    if (!text) return sendErrorResponse(res, "Message text is required.", 400);

    const chat = await findOrCreateUserChatDocument(req.user);
    appendMessage(chat, req.user, text);
    await chat.save();

    const updatedChat = await SupportChat.findById(chat._id).populate(supportChatPopulate);
    const latestMessage = getLatestMessage(updatedChat);

    emitChatUpdated(req, updatedChat, ["support"]);
    emitMessageReceived(req, updatedChat, latestMessage, [getChatRoom(updatedChat)]);

    return sendSuccessResponse(res, updatedChat, "Message sent successfully", 201);
  } catch (error) {
    return sendErrorResponse(res, error.message || "Failed to send message", 500);
  }
};

export const getAllSupportChats = async (req, res) => {
  try {
    if (!ensureAuthenticated(req, res)) return;
    if (!ensureSupportAccess(req, res)) return;

    const chats = await SupportChat.find()
      .populate(supportChatPopulate)
      .sort({ lastMessageAt: -1, updatedAt: -1 });

    return sendSuccessResponse(res, chats, "Support chats fetched successfully");
  } catch (error) {
    return sendErrorResponse(res, error.message || "Failed to fetch support chats", 500);
  }
};

export const getSupportChatById = async (req, res) => {
  try {
    if (!ensureAuthenticated(req, res)) return;

    const chat = await findChatDocumentById(req.params.id);
    if (!chat) return sendErrorResponse(res, "Support chat not found.", 404);
    if (!canAccessChat(chat, req.user)) {
      return sendErrorResponse(res, "You are not allowed to access this support chat.", 403);
    }

    const populatedChat = await SupportChat.findById(chat._id).populate(supportChatPopulate);
    return sendSuccessResponse(res, populatedChat, "Support chat fetched successfully");
  } catch (error) {
    return sendErrorResponse(res, error.message || "Failed to fetch support chat", 500);
  }
};

export const sendSupportReply = async (req, res) => {
  try {
    if (!ensureAuthenticated(req, res)) return;
    if (!ensureSupportAccess(req, res)) return;

    const text = req.body?.text?.trim();
    if (!text) return sendErrorResponse(res, "Reply text is required.", 400);

    const chat = await findChatDocumentById(req.params.id);
    if (!chat) return sendErrorResponse(res, "Support chat not found.", 404);

    if (!chat.assignedSupportAgent) {
      chat.assignedSupportAgent = getUserId(req.user);
    }

    appendMessage(chat, req.user, text);
    chat.messages.forEach((message) => {
      if (!isSupportUser({ role: message.senderRole })) {
        message.readBySupport = true;
      }
    });
    chat.unreadBySupport = 0;

    await chat.save();

    const updatedChat = await SupportChat.findById(chat._id).populate(supportChatPopulate);
    const latestMessage = getLatestMessage(updatedChat);
    const userRoom = getUserRoom(getChatUserId(chat));
    const chatRoom = getChatRoom(updatedChat);

    emitMessageReceived(req, updatedChat, latestMessage, [userRoom, chatRoom]);
    emitChatUpdated(req, updatedChat, ["support"]);

    return sendSuccessResponse(res, updatedChat, "Support reply sent successfully", 201);
  } catch (error) {
    return sendErrorResponse(res, error.message || "Failed to send support reply", 500);
  }
};

export const markSupportChatAsRead = async (req, res) => {
  try {
    if (!ensureAuthenticated(req, res)) return;

    const chat = await findChatDocumentById(req.params.id);
    if (!chat) return sendErrorResponse(res, "Support chat not found.", 404);
    if (!canAccessChat(chat, req.user)) {
      return sendErrorResponse(res, "You are not allowed to update this support chat.", 403);
    }

    if (isSupportUser(req.user)) {
      chat.unreadBySupport = 0;
      chat.messages.forEach((message) => {
        if (!isSupportUser({ role: message.senderRole })) {
          message.readBySupport = true;
        }
      });
    } else {
      chat.unreadByUser = 0;
      chat.messages.forEach((message) => {
        if (isSupportUser({ role: message.senderRole })) {
          message.readByUser = true;
        }
      });
    }

    await chat.save();

    const updatedChat = await SupportChat.findById(chat._id).populate(supportChatPopulate);
    emitChatUpdated(req, updatedChat, [
      "support",
      getUserRoom(getChatUserId(chat)),
      getChatRoom(updatedChat),
    ]);

    return sendSuccessResponse(res, updatedChat, "Support chat marked as read");
  } catch (error) {
    return sendErrorResponse(res, error.message || "Failed to mark support chat as read", 500);
  }
};

export const closeSupportChat = async (req, res) => {
  try {
    if (!ensureAuthenticated(req, res)) return;
    if (!ensureSupportAccess(req, res)) return;

    const chat = await findChatDocumentById(req.params.id);
    if (!chat) return sendErrorResponse(res, "Support chat not found.", 404);

    chat.status = "closed";
    await chat.save();

    const updatedChat = await SupportChat.findById(chat._id).populate(supportChatPopulate);
    emitChatUpdated(req, updatedChat, [
      "support",
      getUserRoom(getChatUserId(chat)),
      getChatRoom(updatedChat),
    ]);

    return sendSuccessResponse(res, updatedChat, "Support chat closed successfully");
  } catch (error) {
    return sendErrorResponse(res, error.message || "Failed to close support chat", 500);
  }
};

export const reopenSupportChat = async (req, res) => {
  try {
    if (!ensureAuthenticated(req, res)) return;
    if (!ensureSupportAccess(req, res)) return;

    const chat = await findChatDocumentById(req.params.id);
    if (!chat) return sendErrorResponse(res, "Support chat not found.", 404);

    chat.status = "open";
    await chat.save();

    const updatedChat = await SupportChat.findById(chat._id).populate(supportChatPopulate);
    emitChatUpdated(req, updatedChat, [
      "support",
      getUserRoom(getChatUserId(chat)),
      getChatRoom(updatedChat),
    ]);

    return sendSuccessResponse(res, updatedChat, "Support chat reopened successfully");
  } catch (error) {
    return sendErrorResponse(res, error.message || "Failed to reopen support chat", 500);
  }
};
