import Ticket from "../models/Ticket.js";

const generateTicketCode = () => {
  return `TK-${Math.floor(1000 + Math.random() * 9000)}`;
};

const generateAvatar = (name) => {
  return name
    .split(" ")
    .map((word) => word[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
};

const getRandomAvatarColor = () => {
  const colors = ["#4A6FDC", "#7048E8", "#0CA678", "#E67700", "#C92A2A"];
  return colors[Math.floor(Math.random() * colors.length)];
};

// GET /api/tickets
export const getTickets = async (req, res) => {
  try {
    const tickets = await Ticket.find().sort({ createdAt: -1 });

    res.status(200).json({
      success: true,
      count: tickets.length,
      data: tickets,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to fetch tickets",
      error: error.message,
    });
  }
};

// GET /api/tickets/:id
export const getTicketById = async (req, res) => {
  try {
    const ticket = await Ticket.findById(req.params.id);

    if (!ticket) {
      return res.status(404).json({
        success: false,
        message: "Ticket not found",
      });
    }

    res.status(200).json({
      success: true,
      data: ticket,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to fetch ticket",
      error: error.message,
    });
  }
};

// POST /api/tickets
export const createTicket = async (req, res) => {
  try {
    const { name, email, subject, priority, message } = req.body;

    if (!name || !email || !subject || !message) {
      return res.status(400).json({
        success: false,
        message: "Name, email, subject, and message are required",
      });
    }

    const ticket = await Ticket.create({
      ticketCode: generateTicketCode(),
      name,
      email,
      subject,
      priority: priority || "medium",
      preview: message.slice(0, 60),
      avatar: generateAvatar(name),
      avatarColor: getRandomAvatarColor(),
      status: "open",
      messages: [
        {
          from: "customer",
          text: message,
        },
      ],
    });

    res.status(201).json({
      success: true,
      message: "Ticket created successfully",
      data: ticket,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to create ticket",
      error: error.message,
    });
  }
};

// POST /api/tickets/:id/messages
export const addMessage = async (req, res) => {
  try {
    const { text, from = "agent" } = req.body;

    if (!text) {
      return res.status(400).json({
        success: false,
        message: "Message text is required",
      });
    }

    const ticket = await Ticket.findById(req.params.id);

    if (!ticket) {
      return res.status(404).json({
        success: false,
        message: "Ticket not found",
      });
    }

    ticket.messages.push({
      from,
      text,
    });

    ticket.preview = text.slice(0, 60);

    await ticket.save();

    res.status(200).json({
      success: true,
      message: "Message added successfully",
      data: ticket,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to add message",
      error: error.message,
    });
  }
};

// PATCH /api/tickets/:id/status
export const updateTicketStatus = async (req, res) => {
  try {
    const { status } = req.body;

    const allowedStatuses = ["open", "pending", "resolved", "closed"];

    if (!allowedStatuses.includes(status)) {
      return res.status(400).json({
        success: false,
        message: "Invalid ticket status",
      });
    }

    const ticket = await Ticket.findByIdAndUpdate(
      req.params.id,
      { status },
      { new: true }
    );

    if (!ticket) {
      return res.status(404).json({
        success: false,
        message: "Ticket not found",
      });
    }

    res.status(200).json({
      success: true,
      message: "Ticket status updated successfully",
      data: ticket,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: "Failed to update ticket status",
      error: error.message,
    });
  }
};