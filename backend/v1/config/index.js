import * as dotenv from "dotenv";
dotenv.config();

const { URI, PORT, SECRET_ACCESS_TOKEN, FRONTEND_URL, NODE_ENV } = process.env;

export { URI, PORT, SECRET_ACCESS_TOKEN, FRONTEND_URL, NODE_ENV };
