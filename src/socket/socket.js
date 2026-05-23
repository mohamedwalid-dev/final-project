import { io } from "socket.io-client";

const SOCKET_URL = "http://localhost:5005";

export const createSocket = () => {
  const token = localStorage.getItem("token");

  return io(SOCKET_URL, {
    auth: { token },
    transports: ["websocket"],
    autoConnect: false,
  });
};

export default createSocket;
