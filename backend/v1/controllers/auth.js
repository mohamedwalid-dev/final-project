import bcrypt from "bcrypt";
import User, { VALID_USER_DEPARTMENTS, VALID_USER_ROLES } from "../models/User.js";
import Blacklist from "../models/Black-List.js";
import { sendSuccess } from "../utils/response.js";
import AppError from "../utils/AppError.js";

const ROLE_TO_DEPARTMENT = {
  client: "client",
  support: "support",
  accountant: "accounting",
  hr: "hr",
  sales: "sales",
  manager: "management",
  admin: "admin",
};

function getCookieOptions() {
  const isProd = process.env.NODE_ENV === "production";
  return {
    maxAge: 20 * 60 * 1000,
    httpOnly: true,
    secure: isProd,
    sameSite: isProd ? "none" : "lax",
  };
}

function sanitizeUser(user) {
  const userObject = typeof user.toObject === "function" ? user.toObject() : { ...user };
  delete userObject.password;
  return userObject;
}

function sendAuthPayload(res, user, token, message, statusCode = 200) {
  const safeUser = sanitizeUser(user);

  return res.status(statusCode).json({
    status: "success",
    success: true,
    data: [{ token, user: safeUser }],
    message,
    token,
    user: safeUser,
  });
}

function normalizeRegisterPayload(body) {
  const name = body.name?.trim();
  const firstName = body.first_name?.trim() || name?.split(/\s+/)[0] || "";
  const lastName =
    body.last_name?.trim() ||
    name?.split(/\s+/).slice(1).join(" ") ||
    firstName;
  const role = body.role || "client";
  const department = body.department || ROLE_TO_DEPARTMENT[role] || "client";

  return {
    name: name || [firstName, lastName].filter(Boolean).join(" ").trim(),
    first_name: firstName,
    last_name: lastName,
    email: body.email?.trim().toLowerCase(),
    password: body.password,
    role,
    department,
    isActive: body.isActive ?? true,
  };
}

export async function register(req, res, next) {
  try {
    const payload = normalizeRegisterPayload(req.body);

    if (!payload.email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
      throw new AppError("A valid email address is required.", 400);
    }

    if (!payload.password || payload.password.length < 8) {
      throw new AppError("Password must be at least 8 characters long.", 400);
    }

    if (!VALID_USER_ROLES.includes(payload.role)) {
      throw new AppError("Invalid user role.", 400);
    }

    if (!VALID_USER_DEPARTMENTS.includes(payload.department)) {
      throw new AppError("Invalid user department.", 400);
    }

    const existingUser = await User.findOne({ email: payload.email });
    if (existingUser) {
      throw new AppError("It seems you already have an account, please log in instead.", 400);
    }

    const hashedPassword = await bcrypt.hash(payload.password, 10);
    const newUser = await User.create({
      ...payload,
      password: hashedPassword,
    });

    const token = newUser.generateAccessJWT();
    res.cookie("SessionID", token, getCookieOptions());

    return sendAuthPayload(
      res,
      newUser,
      token,
      "Thank you for registering with us. Your account has been successfully created.",
      201
    );
  } catch (error) {
    return next(error);
  }
}

export async function login(req, res, next) {
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      throw new AppError("Email and password are required.", 400);
    }

    const user = await User.findOne({ email: email.trim().toLowerCase() }).select("+password");
    if (!user) {
      throw new AppError("Account does not exist", 401);
    }

    const isPasswordValid = await bcrypt.compare(`${password}`, user.password);
    if (!isPasswordValid) {
      throw new AppError(
        "Invalid email or password. Please try again with the correct credentials.",
        401
      );
    }

    if (user.isActive === false) {
      throw new AppError("This account is inactive. Please contact an administrator.", 403);
    }

    const token = user.generateAccessJWT();
    res.cookie("SessionID", token, getCookieOptions());

    return sendAuthPayload(res, user, token, "You are now logged in!", 200);
  } catch (error) {
    return next(error);
  }
}

export async function logout(req, res, next) {
  try {
    const bearerToken = req.headers.authorization?.startsWith("Bearer ")
      ? req.headers.authorization.split(" ")[1]
      : null;
    const accessToken = bearerToken || req.cookies?.SessionID;

    if (accessToken) {
      const checkIfBlacklisted = await Blacklist.findOne({ token: accessToken });
      if (!checkIfBlacklisted) {
        await Blacklist.create({ token: accessToken });
      }
    }

    res.clearCookie("SessionID", getCookieOptions());
    return sendSuccess(res, [], "You are logged out!", 200);
  } catch (error) {
    return next(error);
  }
}

export async function getAuthUsers(req, res, next) {
  try {
    const users = await User.find().select("-password").sort({ createdAt: -1 });
    return sendSuccess(res, users, "Users fetched successfully.", 200);
  } catch (error) {
    return next(error);
  }
}

export async function getInternalUsers(req, res, next) {
  try {
    const users = await User.find({
      isActive: true,
      role: { $ne: "client" },
    })
      .select("-password")
      .sort({ createdAt: -1 });

    return sendSuccess(res, users, "Internal users fetched successfully.", 200);
  } catch (error) {
    return next(error);
  }
}

export async function getUsersByRole(req, res, next) {
  try {
    const { role } = req.params;

    if (!VALID_USER_ROLES.includes(role)) {
      throw new AppError("Invalid user role.", 400);
    }

    const users = await User.find({ role, isActive: true })
      .select("-password")
      .sort({ createdAt: -1 });

    return sendSuccess(res, users, `Active ${role} users fetched successfully.`, 200);
  } catch (error) {
    return next(error);
  }
}

export async function getUsersByDepartment(req, res, next) {
  try {
    const { department } = req.params;

    if (!VALID_USER_DEPARTMENTS.includes(department)) {
      throw new AppError("Invalid user department.", 400);
    }

    const users = await User.find({ department, isActive: true })
      .select("-password")
      .sort({ createdAt: -1 });

    return sendSuccess(
      res,
      users,
      `Active ${department} department users fetched successfully.`,
      200
    );
} catch (error) {
  return res.status(error.statusCode || 500).json({
    status: "failed",
    success: false,
    data: [],
    message: error.message || "Registration failed",
  });
}
}

export async function me(req, res) {
  return sendSuccess(res, req.user ?? [], "Authenticated user", 200);
}

export const Register = register;
export const Login = login;
export const Logout = logout;
export const Me = me;
