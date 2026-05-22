import express from "express";

import {
  getTickets,
  getTicketById,
  createTicket,
  addMessage,
  updateTicketStatus,
} from "../controllers/ticketController.js";

const router = express.Router();

router.get("/", getTickets);
router.get("/:id", getTicketById);
router.post("/", createTicket);
router.post("/:id/messages", addMessage);
router.patch("/:id/status", updateTicketStatus);

export default router;