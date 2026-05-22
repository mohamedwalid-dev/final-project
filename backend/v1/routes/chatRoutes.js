import express from "express";
import {
  addInternalChatMessage,
  addParticipantToInternalChat,
  closeInternalChat,
  createInternalDepartmentChat,
  getInternalChatById,
  getInternalChats,
  getInternalChatsByTicketId,
} from "../controllers/chatController.js";

const router = express.Router();

router.get("/", getInternalChats);
router.get("/ticket/:ticketId", getInternalChatsByTicketId);
router.get("/:id", getInternalChatById);
router.post("/internal", createInternalDepartmentChat);
router.post("/:id/messages", addInternalChatMessage);
router.patch("/:id/participants", addParticipantToInternalChat);
router.patch("/:id/close", closeInternalChat);

export default router;
