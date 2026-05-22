import express from "express";

import {
  getChats,
  getChatById,
  getChatByTicketId,
  createChat,
  addChatMessage,
  updateChatStatus,
  deleteChat,
} from "../controllers/chatController.js";

const router = express.Router();

router.get("/", getChats);
router.get("/ticket/:ticketId", getChatByTicketId);
router.get("/:id", getChatById);

router.post("/", createChat);
router.post("/:id/messages", addChatMessage);

router.patch("/:id/status", updateChatStatus);

router.delete("/:id", deleteChat);

export default router;