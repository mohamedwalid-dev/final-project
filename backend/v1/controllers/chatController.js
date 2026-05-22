import mongoose from "mongoose";
import Chat from "../models/Chat.js";
import Ticket from "../models/Ticket.js";
import User, { VALID_USER_DEPARTMENTS, VALID_USER_ROLES } from "../models/User.js";
import { TICKET_PRIORITIES } from "../models/Ticket.js";
import { sendSuccess } from "../utils/response.js";
import AppError from "../utils/AppError.js";

const chatPopulate = [
  { path: "ticketId", select: "ticketCode clientName clientEmail subject status priority category relatedDepartment" },
  { path: "requestedBy", select: "name first_name last_name email role department isActive" },
  { path: "participants", select: "name first_name last_name email role department isActive" },
];

function ensureInternalAccess(req) {
  if (req.user?.role === "client") {
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

export const getInternalChats = async (req, res, next) => {
  try {
    ensureInternalAccess(req);

    const chats = await Chat.find({ chatType: "internal_department" })
      .populate(chatPopulate)
      .sort({ updatedAt: -1 });

    return sendSuccess(res, chats, "Internal chats fetched successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const getInternalChatById = async (req, res, next) => {
  try {
    ensureInternalAccess(req);

    const chat = await Chat.findById(req.params.id).populate(chatPopulate);
    if (!chat) {
      throw new AppError("Internal chat not found.", 404);
    }

    return sendSuccess(res, chat, "Internal chat fetched successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const getInternalChatsByTicketId = async (req, res, next) => {
  try {
    ensureInternalAccess(req);

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
    ensureInternalAccess(req);

    const {
      ticketId,
      requestedDepartment,
      requestedRole,
      title,
      summary = "",
      participants = [],
      requestedBy,
      priority = "medium",
    } = req.body;

    if (!ticketId || !mongoose.isValidObjectId(ticketId)) {
      throw new AppError("Valid ticket ID is required.", 400);
    }

    if (!requestedDepartment || !VALID_USER_DEPARTMENTS.includes(requestedDepartment)) {
      throw new AppError("Valid requested department is required.", 400);
    }

    if (requestedRole && !VALID_USER_ROLES.includes(requestedRole)) {
      throw new AppError("Invalid requested role.", 400);
    }

    if (!TICKET_PRIORITIES.includes(priority)) {
      throw new AppError("Invalid chat priority.", 400);
    }

    const ticket = await Ticket.findById(ticketId);
    if (!ticket) {
      throw new AppError("Ticket not found.", 404);
    }

    const requestedById = requestedBy || req.user?._id || ticket.assignedSupportAgent;
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

    const chat = await Chat.create({
      ticketId: ticket._id,
      chatType: "internal_department",
      title: title || `Internal help for ${ticket.ticketCode}`,
      requestedBy: requestedById,
      requestedDepartment,
      requestedRole,
      participants: activeInternalUsers.map((user) => user._id),
      status: "active",
      priority,
      summary,
      messages: [],
    });

    const populatedChat = await Chat.findById(chat._id).populate(chatPopulate);
    return sendSuccess(res, populatedChat, "Internal department chat created successfully.", 201);
  } catch (error) {
    return next(error);
  }
};

export const addInternalChatMessage = async (req, res, next) => {
  try {
    ensureInternalAccess(req);

    const {
      senderId,
      senderRole,
      senderDepartment,
      senderName,
      text,
      message,
      isInternalNote = true,
      attachments = [],
    } = req.body;
    const resolvedText = text || message;

    if (!resolvedText) {
      throw new AppError("Internal message text is required.", 400);
    }

    const resolvedRole = senderRole || req.user?.role;
    const resolvedDepartment = senderDepartment || req.user?.department;

    if (!VALID_USER_ROLES.includes(resolvedRole)) {
      throw new AppError("Valid sender role is required.", 400);
    }

    if (!VALID_USER_DEPARTMENTS.includes(resolvedDepartment)) {
      throw new AppError("Valid sender department is required.", 400);
    }

    const chat = await Chat.findById(req.params.id);
    if (!chat) {
      throw new AppError("Internal chat not found.", 404);
    }

    chat.messages.push({
      senderId: senderId || req.user?._id,
      senderRole: resolvedRole,
      senderDepartment: resolvedDepartment,
      senderName: senderName || getDisplayName(req.user),
      text: resolvedText,
      isInternalNote,
      attachments,
    });

    await chat.save();

    const populatedChat = await Chat.findById(chat._id).populate(chatPopulate);
    return sendSuccess(res, populatedChat, "Internal chat message added successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const addParticipantToInternalChat = async (req, res, next) => {
  try {
    ensureInternalAccess(req);

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

    const chat = await Chat.findById(req.params.id);
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
    ensureInternalAccess(req);

    const chat = await Chat.findByIdAndUpdate(
      req.params.id,
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
