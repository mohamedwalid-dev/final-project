import express from "express";
import { check } from "express-validator";

import {
  getAuthUsers,
  getInternalUsers,
  getUsersByDepartment,
  getUsersByRole,
  login,
  logout,
  me,
  register,
} from "../controllers/auth.js";

import validateRequest from "../middleware/validateRequest.js";
import { Verify } from "../middleware/verify.js";

const router = express.Router();

router.post(
  "/register",
  check("email")
    .isEmail()
    .withMessage("Enter a valid email address")
    .normalizeEmail(),
  check("password")
    .notEmpty()
    .isLength({ min: 8 })
    .withMessage("Must be at least 8 chars long"),
  validateRequest,
  register
);

router.post(
  "/login",
  check("email")
    .isEmail()
    .withMessage("Enter a valid email address")
    .normalizeEmail(),
  check("password").not().isEmpty(),
  validateRequest,
  login
);

router.post("/logout", logout);
router.get("/logout", logout);

router.get("/me", Verify, me);

router.get("/users/internal", Verify, getInternalUsers);
router.get("/users/role/:role", Verify, getUsersByRole);
router.get("/users/department/:department", Verify, getUsersByDepartment);
router.get("/users", Verify, getAuthUsers);

export default router;