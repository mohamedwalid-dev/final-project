import cors from "cors";
import cookieParser from "cookie-parser";
import express from "express";
import mongoose from "mongoose";

import { FRONTEND_URL, PORT, URI } from "./config/index.js";
import errorHandler from "./middleware/errorHandler.js";
import notFound from "./middleware/notFound.js";
import Router from "./routes/index.js";


const server = express();

server.disable("x-powered-by");
server.use(cookieParser());
server.use(express.urlencoded({ extended: true }));
server.use(express.json());

const corsOrigin = FRONTEND_URL || "http://localhost:5173";
server.use(cors({ origin: corsOrigin, credentials: true }));

mongoose.set("strictQuery", false);

async function connectDB() {
  await mongoose.connect(URI);
  console.log("Connected to database");
}

connectDB().catch((err) => {
  console.error(err);
  process.exit(1);
});

Router(server);

server.use(notFound);
server.use(errorHandler);

server.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));

