import { sendFailed } from "../utils/response.js";

export default function errorHandler(err, req, res, next) { // eslint-disable-line
  const statusCode = Number(err?.statusCode) || 500;
  const message =
    err?.message ||
    (statusCode === 500 ? "Internal Server Error" : "Request failed");

  const data = Array.isArray(err?.validationErrors) ? err.validationErrors : [];
  return sendFailed(res, message, statusCode, data);
}
