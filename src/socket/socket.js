import { io } from "socket.io-client";

const rawSocketUrl = import.meta.env.VITE_API_URL || "http://localhost:5005";
const SOCKET_URL = rawSocketUrl.replace(/\/v1\/?$/, "").replace(/\/$/, "");

const getSocketAuth = () => {
  const token = localStorage.getItem("token");

  return token ? { token } : {};
};

export const socket = io(SOCKET_URL, {
  auth: getSocketAuth(),
  withCredentials: true,
  transports: ["websocket", "polling"],
  autoConnect: false,
});

export const connectSocket = () => {
  socket.auth = getSocketAuth();
  if (!socket.connected) socket.connect();
  return socket;
};

export const createSocket = () => {
  socket.auth = getSocketAuth();
  return socket;
};

export default createSocket;
