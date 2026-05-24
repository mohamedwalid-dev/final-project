import mongoose from "mongoose";
import Chat from "../models/Chat.js";
import Ticket from "../models/Ticket.js";
import User, { VALID_USER_DEPARTMENTS, VALID_USER_ROLES } from "../models/User.js";
import { TICKET_PRIORITIES } from "../models/Ticket.js";
import { sendSuccess } from "../utils/response.js";
import AppError from "../utils/AppError.js";

const chatPopulate = [
  {
    path: "ticketId",
    select: "ticketCode clientName clientEmail subject status priority category relatedDepartment",
  },
  { path: "requestedBy", select: "name first_name last_name email role department isActive" },
  { path: "participants", select: "name first_name last_name email role department isActive" },
];

const getUserId = (user) => user?._id || user?.id;

const isSupportOrAdmin = (user) =>
  user?.role === "admin" || (user?.role === "support" && user?.department === "support");

function ensureInternalAccess(user) {
  if (user?.role === "client") {
    throw new AppError("Clients cannot access internal department chats.", 403);
  }
}

function getDisplayName(user, fallback = "Internal User") {
  return (
    user?.name ||
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    fallback
  );
}

function cleanParticipantIds(ids = []) {
  return [...new Set(ids.filter((id) => mongoose.isValidObjectId(id)).map(String))];
}

function hasMatchingId(value, target) {
  if (!value || !target) return false;
  return String(value?._id || value) === String(target);
}

function canAccessInternalChat(user, chat) {
  if (!chat || user?.role === "client") return false;
  if (isSupportOrAdmin(user)) return true;

  const userId = getUserId(user);
  const userDepartment = user?.department;
  const ticketDepartment = chat.ticketId?.relatedDepartment || chat.ticketId?.department;

  return (
    chat.requestedDepartment === userDepartment ||
    ticketDepartment === userDepartment ||
    hasMatchingId(chat.requestedBy, userId) ||
    (chat.participants || []).some((participant) => hasMatchingId(participant, userId))
  );
}

function ensureCanAccessInternalChat(user, chat) {
  if (!canAccessInternalChat(user, chat)) {
    throw new AppError("You are not allowed to access this internal chat.", 403);
  }
}

function ensureCanViewTicket(user, ticket) {
  if (isSupportOrAdmin(user)) return;

  if (ticket?.relatedDepartment !== user?.department) {
    throw new AppError("You are not allowed to access this ticket chat.", 403);
  }
}

function getInternalChatQuery(user) {
  const baseQuery = { chatType: "internal_department" };
  if (isSupportOrAdmin(user)) return baseQuery;

  const userId = getUserId(user);
  return {
    ...baseQuery,
    $or: [
      { requestedDepartment: user?.department },
      { requestedBy: userId },
      { participants: userId },
    ].filter((condition) => Object.values(condition)[0]),
  };
}

function createMessageFromUser(user, text, attachments = []) {
  const senderRole = user?.role;
  const senderDepartment = user?.department;

  if (!VALID_USER_ROLES.includes(senderRole)) {
    throw new AppError("Valid sender role is required.", 400);
  }

  if (!VALID_USER_DEPARTMENTS.includes(senderDepartment)) {
    throw new AppError("Valid sender department is required.", 400);
  }

  return {
    senderId: getUserId(user),
    senderRole,
    senderDepartment,
    senderName: getDisplayName(user),
    text,
    isInternalNote: true,
    attachments: Array.isArray(attachments) ? attachments : [],
  };
}

function getLatestMessage(chat) {
  const messages = chat?.messages || [];
  return messages[messages.length - 1];
}

function toPayload(document) {
  return document?.toObject ? document.toObject() : document;
}

function emitInternalChatMessage(req, chat, message) {
  const io = req.app.get("io");
  if (!io || !chat?._id || !message) return;

  const roomId = String(chat._id);
  const ticketId = chat.ticketId?._id || chat.ticketId;

  console.log("Sending real-time message to room:", roomId);
  console.log("Saved message:", toPayload(message));

  io.to(roomId).emit("newInternalChatMessage", {
    chatId: roomId,
    ticketId: ticketId ? String(ticketId) : "",
    message: toPayload(message),
  });
}

export const getInternalChats = async (req, res, next) => {
  try {
    ensureInternalAccess(req.user);

    const chats = await Chat.find(getInternalChatQuery(req.user))
      .populate(chatPopulate)
      .sort({ updatedAt: -1 });

    return sendSuccess(res, chats, "Internal chats fetched successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const getInternalChatById = async (req, res, next) => {
  try {
    ensureInternalAccess(req.user);

    const chat = await Chat.findById(req.params.id).populate(chatPopulate);
    if (!chat) {
      throw new AppError("Internal chat not found.", 404);
    }

    ensureCanAccessInternalChat(req.user, chat);

    return sendSuccess(res, chat, "Internal chat fetched successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const getInternalChatsByTicketId = async (req, res, next) => {
  try {
    ensureInternalAccess(req.user);

    if (!mongoose.isValidObjectId(req.params.ticketId)) {
      throw new AppError("Valid ticket ID is required.", 400);
    }

    const ticket = await Ticket.findById(req.params.ticketId);
    if (!ticket) {
      throw new AppError("Ticket not found.", 404);
    }

    ensureCanViewTicket(req.user, ticket);

    const chats = await Chat.find({
      ticketId: req.params.ticketId,
      chatType: "internal_department",
    })
      .populate(chatPopulate)
      .sort({ updatedAt: -1 });

    return sendSuccess(res, chats, "Ticket internal chats fetched successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const createInternalDepartmentChat = async (req, res, next) => {
  try {
    ensureInternalAccess(req.user);

    const {
      ticketId,
      requestedDepartment,
      requestedRole,
      title,
      summary = "",
      participants = [],
      priority,
      text,
      description,
    } = req.body;

    if (!ticketId || !mongoose.isValidObjectId(ticketId)) {
      throw new AppError("Valid ticket ID is required.", 400);
    }

    if (requestedRole && !VALID_USER_ROLES.includes(requestedRole)) {
      throw new AppError("Invalid requested role.", 400);
    }

    const ticket = await Ticket.findById(ticketId);
    if (!ticket) {
      throw new AppError("Ticket not found.", 404);
    }

    ensureCanViewTicket(req.user, ticket);

    const resolvedRequestedDepartment = requestedDepartment || ticket.relatedDepartment;
    if (
      !resolvedRequestedDepartment ||
      !VALID_USER_DEPARTMENTS.includes(resolvedRequestedDepartment)
    ) {
      throw new AppError("Valid requested department is required.", 400);
    }

    const resolvedPriority = priority || ticket.priority || "medium";
    if (!TICKET_PRIORITIES.includes(resolvedPriority)) {
      throw new AppError("Invalid chat priority.", 400);
    }

    const requestedById = getUserId(req.user) || ticket.assignedSupportAgent;
    if (requestedById && !mongoose.isValidObjectId(requestedById)) {
      throw new AppError("Invalid requestedBy user ID.", 400);
    }

    const participantIds = cleanParticipantIds(participants);
    if (requestedById) participantIds.push(String(requestedById));

    const activeInternalUsers = participantIds.length
      ? await User.find({
          _id: { $in: cleanParticipantIds(participantIds) },
          isActive: true,
          role: { $ne: "client" },
        }).select("_id")
      : [];

    let chat = await Chat.findOne({
      ticketId: ticket._id,
      chatType: "internal_department",
    });

    if (chat) {
      if (requestedById) chat.participants.addToSet(requestedById);
      await chat.save();
      const populatedChat = await Chat.findById(chat._id).populate(chatPopulate);
      return sendSuccess(res, populatedChat, "Internal department chat fetched successfully.", 200);
    }

    const initialText = (text || description || summary || ticket.description || "").trim();
    if (!initialText) {
      throw new AppError("Initial internal message text is required.", 400);
    }

    chat = await Chat.create({
      ticketId: ticket._id,
      chatType: "internal_department",
      title: title || ticket.subject || `Internal help for ${ticket.ticketCode}`,
      requestedBy: requestedById,
      requestedDepartment: resolvedRequestedDepartment,
      requestedRole: requestedRole || req.user?.role,
      participants: activeInternalUsers.map((user) => user._id),
      status: "active",
      priority: resolvedPriority,
      summary: summary || initialText,
      messages: [createMessageFromUser(req.user, initialText, req.body.attachments)],
    });

    const populatedChat = await Chat.findById(chat._id).populate(chatPopulate);
    return sendSuccess(res, populatedChat, "Internal department chat created successfully.", 201);
  } catch (error) {
    return next(error);
  }
};

export const addInternalChatMessage = async (req, res, next) => {
  try {
    ensureInternalAccess(req.user);

    const text = req.body?.text?.trim();
    const attachments = Array.isArray(req.body?.attachments) ? req.body.attachments : [];

    if (!text) {
      throw new AppError("Internal message text is required.", 400);
    }

    const accessChat = await Chat.findById(req.params.id).populate(chatPopulate);
    if (!accessChat) {
      throw new AppError("Internal chat not found.", 404);
    }

    ensureCanAccessInternalChat(req.user, accessChat);

    const chat = await Chat.findById(accessChat._id);
    if (!chat) {
      throw new AppError("Internal chat not found.", 404);
    }

    const newMessage = createMessageFromUser(req.user, text, attachments);
    chat.messages.push(newMessage);
    chat.summary = text;
    chat.participants.addToSet(getUserId(req.user));
    await chat.save();

    const savedMessage = getLatestMessage(chat);
    const populatedChat = await Chat.findById(chat._id).populate(chatPopulate);
    emitInternalChatMessage(req, chat, savedMessage);

    return sendSuccess(res, populatedChat, "Internal chat message added successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const addParticipantToInternalChat = async (req, res, next) => {
  try {
    ensureInternalAccess(req.user);

    const participantId = req.body.participantId || req.body.userId;
    if (!participantId || !mongoose.isValidObjectId(participantId)) {
      throw new AppError("Valid participant ID is required.", 400);
    }

    const participant = await User.findOne({
      _id: participantId,
      isActive: true,
      role: { $ne: "client" },
    }).select("-password");

    if (!participant) {
      throw new AppError("Internal participant not found.", 404);
    }

    const accessChat = await Chat.findById(req.params.id).populate(chatPopulate);
    if (!accessChat) {
      throw new AppError("Internal chat not found.", 404);
    }

    ensureCanAccessInternalChat(req.user, accessChat);

    const chat = await Chat.findById(accessChat._id);
    if (!chat) {
      throw new AppError("Internal chat not found.", 404);
    }

    chat.participants.addToSet(participant._id);
    await chat.save();

    const populatedChat = await Chat.findById(chat._id).populate(chatPopulate);
    return sendSuccess(res, populatedChat, "Participant added successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const closeInternalChat = async (req, res, next) => {
  try {
    ensureInternalAccess(req.user);

    const existingChat = await Chat.findById(req.params.id).populate(chatPopulate);
    if (!existingChat) {
      throw new AppError("Internal chat not found.", 404);
    }

    ensureCanAccessInternalChat(req.user, existingChat);

    const chat = await Chat.findByIdAndUpdate(
      existingChat._id,
      { status: "closed" },
      { new: true, runValidators: true }
    ).populate(chatPopulate);
    if (!chat) {
      throw new AppError("Internal chat not found.", 404);
    }

    return sendSuccess(res, chat, "Internal chat closed successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const getChats = getInternalChats;
export const getChatById = getInternalChatById;
export const getChatByTicketId = getInternalChatsByTicketId;
export const createChat = createInternalDepartmentChat;
export const addChatMessage = addInternalChatMessage;
