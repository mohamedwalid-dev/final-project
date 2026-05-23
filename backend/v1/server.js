import cors from "cors";
import cookieParser from "cookie-parser";
import express from "express";
import http from "http";
import mongoose from "mongoose";
import process from "node:process";
import { Server } from "socket.io";

import { FRONTEND_URL, PORT, URI } from "./config/index.js";
import errorHandler from "./middleware/errorHandler.js";
import notFound from "./middleware/notFound.js";
import Router from "./routes/index.js";
import initializeSupportChatSocket from "./socket/supportChatSocket.js";


const app = express();
const httpServer = http.createServer(app);
const corsOrigins = Array.from(
  new Set([FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"].filter(Boolean))
);

const io = new Server(httpServer, {
  cors: {
    origin: corsOrigins,
    methods: ["GET", "POST", "PATCH"],
    credentials: true,
  },
});

app.set("io", io);
initializeSupportChatSocket(io);

app.disable("x-powered-by");
app.use(cookieParser());
app.use(express.urlencoded({ extended: true }));
app.use(express.json());

app.use(cors({ origin: corsOrigins, credentials: true }));

mongoose.set("strictQuery", false);

async function connectDB() {
  await mongoose.connect(URI);
  console.log("Connected to database");
}

connectDB().catch((err) => {
  console.error(err);
  process.exit(1);
});

Router(app);

app.use(notFound);
app.use(errorHandler);

httpServer.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));
