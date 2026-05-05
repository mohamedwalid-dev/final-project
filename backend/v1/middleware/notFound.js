import { sendFailed } from "../utils/response.js";

export default function notFound(req, res, next) { // eslint-disable-line
  return sendFailed(res, `Route not found: ${req.method} ${req.originalUrl}`, 404, []);
}

