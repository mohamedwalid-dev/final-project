import { validationResult } from "express-validator";
import AppError from "../utils/AppError.js";

export default function validateRequest(req, res, next) {
  const errors = validationResult(req);
  if (errors.isEmpty()) return next();

  const list = errors.array({ onlyFirstError: true }).map((e) => ({
    field: e.path,
    message: e.msg,
  }));

  const first = list[0]?.message ?? "Validation failed";
  const err = new AppError(first, 400);
  err.validationErrors = list;
  return next(err);
}

