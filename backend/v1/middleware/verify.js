import jwt from "jsonwebtoken";
import User from "../models/User.js";
import Blacklist from "../models/Black-List.js";
import { SECRET_ACCESS_TOKEN } from "../config/index.js";
import AppError from "../utils/AppError.js";

export async function Verify(req, res, next) {
  const accessToken = req.cookies?.SessionID;
  if (!accessToken) return next(new AppError("Not authenticated", 401));

  const checkIfBlacklisted = await Blacklist.findOne({ token: accessToken });
  if (checkIfBlacklisted) return next(new AppError("Session expired. Please login again.", 401));

  try {
    const decoded = jwt.verify(accessToken, SECRET_ACCESS_TOKEN);
    const user = await User.findById(decoded?.id);
    if (!user) return next(new AppError("Not authenticated", 401));
    const { password, ...data } = user._doc;
    req.user = data;
    return next();
  } catch {
    return next(new AppError("Session expired. Please login again.", 401));
  }
}

export function VerifyRole(req, res, next) {
  const role = req.user?.role;
  if (role !== "0x88") return next(new AppError("You are not authorized to view this page.", 401));
  return next();
}
