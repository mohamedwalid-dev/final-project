export function sendSuccess(res, data = [], message = "Success", statusCode = 200) {
  return res.status(statusCode).json({
    status: "success",
    data: Array.isArray(data) ? data : [data],
    message,
  });
}

export function sendFailed(res, message = "Request failed", statusCode = 400, data = []) {
  return res.status(statusCode).json({
    status: "failed",
    data: Array.isArray(data) ? data : [data],
    message,
  });
}

