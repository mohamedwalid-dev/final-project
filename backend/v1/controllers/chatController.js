import Chat from "../models/Chat.js";
import Ticket from "../models/Ticket.js";

// GET /v1/chats
export const getChats = async (req, res) => {
  try {
    const chats = await Chat.find()
      .populate("ticketId")
      .sort({ updatedAt: -1 });

    res.status(200).json({
      success: true,
      count: chats.length,
      data: chats,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to fetch chats",
      error: error.message,
    });
  }
};

// GET /v1/chats/:id
export const getChatById = async (req, res) => {
  try {
    const chat = await Chat.findById(req.params.id).populate("ticketId");

    if (!chat) {
      return res.status(404).json({
        success: false,
        message: "Chat not found",
      });
    }

    res.status(200).json({
      success: true,
      data: chat,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to fetch chat",
      error: error.message,
    });
  }
};

// GET /v1/chats/ticket/:ticketId
export const getChatByTicketId = async (req, res) => {
  try {
    const chat = await Chat.findOne({
      ticketId: req.params.ticketId,
    }).populate("ticketId");

    if (!chat) {
      return res.status(404).json({
        success: false,
        message: "Chat not found for this ticket",
      });
    }

    res.status(200).json({
      success: true,
      data: chat,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to fetch ticket chat",
      error: error.message,
    });
  }
};

// POST /v1/chats
export const createChat = async (req, res) => {
  try {
    const { ticketId } = req.body;

    if (!ticketId) {
      return res.status(400).json({
        success: false,
        message: "Ticket ID is required",
      });
    }

    const ticket = await Ticket.findById(ticketId);

    if (!ticket) {
      return res.status(404).json({
        success: false,
        message: "Ticket not found",
      });
    }

    const existingChat = await Chat.findOne({ ticketId });

    if (existingChat) {
      return res.status(200).json({
        success: true,
        message: "Chat already exists for this ticket",
        data: existingChat,
      });
    }

    const chat = await Chat.create({
      ticketId: ticket._id,
      ticketCode: ticket.ticketCode,
      customerName: ticket.name,
      customerEmail: ticket.email,
      messages: ticket.messages.map((msg) => ({
        senderType: msg.from,
        senderName: msg.from === "agent" ? "Support Agent" : ticket.name,
        message: msg.text,
      })),
    });

    res.status(201).json({
      success: true,
      message: "Chat created successfully",
      data: chat,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to create chat",
      error: error.message,
    });
  }
};

// POST /v1/chats/:id/messages
export const addChatMessage = async (req, res) => {
  try {
    const {
      senderType = "agent",
      senderName = "Support Agent",
      message,
      isInternalNote = false,
      attachments = [],
    } = req.body;

    if (!message) {
      return res.status(400).json({
        success: false,
        message: "Message is required",
      });
    }

    const chat = await Chat.findById(req.params.id);

    if (!chat) {
      return res.status(404).json({
        success: false,
        message: "Chat not found",
      });
    }

    chat.messages.push({
      senderType,
      senderName,
      message,
      isInternalNote,
      attachments,
    });

    await chat.save();

    res.status(200).json({
      success: true,
      message: "Message added successfully",
      data: chat,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to add chat message",
      error: error.message,
    });
  }
};

// PATCH /v1/chats/:id/status
export const updateChatStatus = async (req, res) => {
  try {
    const { status } = req.body;

    const allowedStatuses = ["active", "closed"];

    if (!allowedStatuses.includes(status)) {
      return res.status(400).json({
        success: false,
        message: "Invalid chat status",
      });
    }

    const chat = await Chat.findByIdAndUpdate(
      req.params.id,
      { status },
      { new: true }
    );

    if (!chat) {
      return res.status(404).json({
        success: false,
        message: "Chat not found",
      });
    }

    res.status(200).json({
      success: true,
      message: "Chat status updated successfully",
      data: chat,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to update chat status",
      error: error.message,
    });
  }
};

// DELETE /v1/chats/:id
export const deleteChat = async (req, res) => {
  try {
    const chat = await Chat.findByIdAndDelete(req.params.id);

    if (!chat) {
      return res.status(404).json({
        success: false,
        message: "Chat not found",
      });
    }

    res.status(200).json({
      success: true,
      message: "Chat deleted successfully",
      data: chat,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to delete chat",
      error: error.message,
    });
  }
};