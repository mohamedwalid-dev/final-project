import express from "express";
import {
  closeSupportChat,
  getAllSupportChats,
  getMySupportChat,
  getSupportChatById,
  markSupportChatAsRead,
  reopenSupportChat,
  sendMySupportMessage,
  sendSupportReply,
} from "../controllers/supportChatController.js";

const router = express.Router();

router.get("/me", getMySupportChat);
router.post("/me/messages", sendMySupportMessage);

router.get("/", getAllSupportChats);
router.get("/:id", getSupportChatById);
router.post("/:id/reply", sendSupportReply);
router.patch("/:id/read", markSupportChatAsRead);
router.patch("/:id/close", closeSupportChat);
router.patch("/:id/reopen", reopenSupportChat);

export default router;
