import express from "express";
import { check } from "express-validator";
import { Login, Logout, Me, Register } from "../controllers/auth.js";
import validateRequest from "../middleware/validateRequest.js";
import { Verify } from "../middleware/verify.js";

const router = express.Router();

// Register route -- POST request
router.post(
    "/register",
    check("email")
        .isEmail()
        .withMessage("Enter a valid email address")
        .normalizeEmail(),
    check("first_name")
        .not()
        .isEmpty()
        .withMessage("You first name is required")
        .trim()
        .escape(),
    check("last_name")
        .not()
        .isEmpty()
        .withMessage("You last name is required")
        .trim()
        .escape(),
    check("password")
        .notEmpty()
        .isLength({ min: 8 })
        .withMessage("Must be at least 8 chars long"),
    validateRequest,
    Register
);

// Login route == POST request
router.post(
    "/login",
    check("email")
        .isEmail()
        .withMessage("Enter a valid email address")
        .normalizeEmail(),
    check("password").not().isEmpty(),
    validateRequest,
    Login
);

router.post("/logout", Logout);
router.get("/logout", Logout); // backwards compatibility

router.get("/me", Verify, Me);

export default router;
