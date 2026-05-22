import Ticket, {
  TICKET_CATEGORIES,
  TICKET_PRIORITIES,
  TICKET_STATUSES,
} from "../models/Ticket.js";
import User, { VALID_USER_DEPARTMENTS } from "../models/User.js";
import { sendSuccess } from "../utils/response.js";
import AppError from "../utils/AppError.js";

const CATEGORY_DEPARTMENT_MAP = {
  invoice: "accounting",
  payment: "finance",
  hr: "hr",
  technical: "support",
  sales: "sales",
  general: "support",
};

const createTicketCode = () => {
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const random = Math.floor(1000 + Math.random() * 9000);
  return `TK-${date}-${random}`;
};

const createUniqueTicketCode = async () => {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const ticketCode = createTicketCode();
    const exists = await Ticket.exists({ ticketCode });
    if (!exists) return ticketCode;
  }

  return `TK-${Date.now()}`;
};

const trimPreview = (text = "") => text.trim().slice(0, 140);

const ticketPopulate = [
  { path: "clientId", select: "name first_name last_name email role department isActive" },
  {
    path: "assignedSupportAgent",
    select: "name first_name last_name email role department isActive",
  },
];

export const getTickets = async (req, res, next) => {
  try {
    const tickets = await Ticket.find().populate(ticketPopulate).sort({ createdAt: -1 });
    return sendSuccess(res, tickets, "Tickets fetched successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const getTicketById = async (req, res, next) => {
  try {
    const ticket = await Ticket.findById(req.params.id).populate(ticketPopulate);

    if (!ticket) {
      throw new AppError("Ticket not found.", 404);
    }

    return sendSuccess(res, ticket, "Ticket fetched successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const createTicket = async (req, res, next) => {
  try {
    const {
      clientId,
      clientName,
      clientEmail,
      name,
      email,
      subject,
      description,
      message,
      priority = "medium",
      category = "general",
      relatedDepartment,
      attachments = [],
    } = req.body;

    const resolvedDescription = description || message;
    const resolvedClientName = clientName || name || req.user?.name;
    const resolvedClientEmail = clientEmail || email || req.user?.email;
    const resolvedClientId = clientId || (req.user?.role === "client" ? req.user?._id : undefined);
    const resolvedDepartment = relatedDepartment || CATEGORY_DEPARTMENT_MAP[category] || "support";

    if (!resolvedClientName || !resolvedClientEmail || !subject || !resolvedDescription) {
      throw new AppError("Client name, client email, subject, and description are required.", 400);
    }

    if (!TICKET_PRIORITIES.includes(priority)) {
      throw new AppError("Invalid ticket priority.", 400);
    }

    if (!TICKET_CATEGORIES.includes(category)) {
      throw new AppError("Invalid ticket category.", 400);
    }

    if (!VALID_USER_DEPARTMENTS.includes(resolvedDepartment)) {
      throw new AppError("Invalid related department.", 400);
    }

    const ticket = await Ticket.create({
      ticketCode: await createUniqueTicketCode(),
      clientId: resolvedClientId,
      clientName: resolvedClientName,
      clientEmail: resolvedClientEmail,
      subject,
      description: resolvedDescription,
      priority,
      status: "open",
      category,
      relatedDepartment: resolvedDepartment,
      preview: trimPreview(resolvedDescription),
      messages: [
        {
          senderId: resolvedClientId,
          senderType: "client",
          senderName: resolvedClientName,
          text: resolvedDescription,
          attachments,
        },
      ],
    });

    const populatedTicket = await Ticket.findById(ticket._id).populate(ticketPopulate);
    return sendSuccess(res, populatedTicket, "Ticket created successfully.", 201);
  } catch (error) {
    return next(error);
  }
};

export const addTicketMessage = async (req, res, next) => {
  try {
    const {
      senderId,
      senderType,
      senderName,
      text,
      message,
      attachments = [],
    } = req.body;
    const resolvedText = text || message;

    if (!resolvedText) {
      throw new AppError("Message text is required.", 400);
    }

    const ticket = await Ticket.findById(req.params.id);
    if (!ticket) {
      throw new AppError("Ticket not found.", 404);
    }

    const resolvedSenderType =
      senderType || (req.user?.role === "client" ? "client" : "support");

    if (!["client", "support", "system"].includes(resolvedSenderType)) {
      throw new AppError("Invalid message sender type.", 400);
    }

    ticket.messages.push({
      senderId: senderId || req.user?._id,
      senderType: resolvedSenderType,
      senderName:
        senderName ||
        req.user?.name ||
        [req.user?.first_name, req.user?.last_name].filter(Boolean).join(" ") ||
        (resolvedSenderType === "client" ? ticket.clientName : "Support Team"),
      text: resolvedText,
      attachments,
    });
    ticket.preview = trimPreview(resolvedText);

    await ticket.save();

    const populatedTicket = await Ticket.findById(ticket._id).populate(ticketPopulate);
    return sendSuccess(res, populatedTicket, "Ticket message added successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const updateTicketStatus = async (req, res, next) => {
  try {
    const { status } = req.body;

    if (!TICKET_STATUSES.includes(status)) {
      throw new AppError("Invalid ticket status.", 400);
    }

    const ticket = await Ticket.findByIdAndUpdate(
      req.params.id,
      { status },
      { new: true, runValidators: true }
    ).populate(ticketPopulate);

    if (!ticket) {
      throw new AppError("Ticket not found.", 404);
    }

    return sendSuccess(res, ticket, "Ticket status updated successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const assignTicketToSupportAgent = async (req, res, next) => {
  try {
    const { agentId } = req.body;

    if (!agentId) {
      throw new AppError("Support agent ID is required.", 400);
    }

    const agent = await User.findById(agentId).select("-password");
    if (!agent) {
      throw new AppError("Support agent not found.", 404);
    }

    const ticket = await Ticket.findByIdAndUpdate(
      req.params.id,
      { assignedSupportAgent: agent._id },
      { new: true, runValidators: true }
    ).populate(ticketPopulate);

    if (!ticket) {
      throw new AppError("Ticket not found.", 404);
    }

    return sendSuccess(res, ticket, "Ticket assigned successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const updateTicketDepartment = async (req, res, next) => {
  try {
    const { relatedDepartment } = req.body;

    if (!VALID_USER_DEPARTMENTS.includes(relatedDepartment)) {
      throw new AppError("Invalid related department.", 400);
    }

    const ticket = await Ticket.findByIdAndUpdate(
      req.params.id,
      { relatedDepartment },
      { new: true, runValidators: true }
    ).populate(ticketPopulate);

    if (!ticket) {
      throw new AppError("Ticket not found.", 404);
    }

    return sendSuccess(res, ticket, "Ticket department updated successfully.", 200);
  } catch (error) {
    return next(error);
  }
};

export const addMessage = addTicketMessage;
