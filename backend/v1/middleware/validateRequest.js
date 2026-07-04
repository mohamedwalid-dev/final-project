import { validationResult } from "express-validator";

export default function validateRequest(req, res, next) {
  const errors = validationResult(req);

  if (errors.isEmpty()) {
    return next();
  }

  const list = errors.array({ onlyFirstError: true }).map((e) => ({
    field: e.path,
    message: e.msg,
  }));

  const first = list[0]?.message || "Validation failed";

  return res.status(400).json({
    status: "failed",
    success: false,
    data: [],
    message: first,
    errors: list,
  });
}