import express from "express";
import {
  addTicketMessage,
  assignTicketToSupportAgent,
  createTicket,
  getTicketById,
  getTickets,
  updateTicketDepartment,
  updateTicketStatus,
} from "../controllers/ticketController.js";

const router = express.Router();

router.get("/", getTickets);
router.get("/:id", getTicketById);
router.post("/", createTicket);
router.post("/:id/messages", addTicketMessage);
router.patch("/:id/status", updateTicketStatus);
router.patch("/:id/assign", assignTicketToSupportAgent);
router.patch("/:id/department", updateTicketDepartment);

export default router;
