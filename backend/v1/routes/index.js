import Auth from "./auth.js";
import EmployeeRoutes from "./employee.routes.js";
import LeadRoutes from "./lead.routes.js";
import InvoiceRoutes from "./invoice.routes.js";
import chatRoutes from "./chatRoutes.js";
import supportChatRoutes from "./supportChatRoutes.js";
import ticketRoutes from "./ticketRoutes.js";
import { Verify, VerifyRole } from "../middleware/verify.js";
import { sendSuccess } from "../utils/response.js";
import inventoryRoutes from "./inventoryRoutes.js";

const Router = (server) => {
  server.get("/v1", (req, res) => {
    return sendSuccess(res, [], "Welcome to our API homepage!", 200);
  });

  server.use("/v1/auth", Auth);

  server.use("/v1/employees", Verify, EmployeeRoutes);

  server.use("/v1/leads", Verify, LeadRoutes);

  server.use("/v1/invoices", Verify, InvoiceRoutes);

  server.use("/v1/tickets", Verify, ticketRoutes);

  server.use("/v1/chats", Verify, chatRoutes);

  server.use("/v1/support-chats", Verify, supportChatRoutes);

  server.use("/v1/inventory", inventoryRoutes);

  server.get("/v1/user", Verify, (req, res) => {
    return sendSuccess(res, [], "Welcome to your Dashboard!", 200);
  });

  server.get("/v1/admin", Verify, VerifyRole, (req, res) => {
    return sendSuccess(res, [], "Welcome to the Admin portal!", 200);
  });
};

export default Router;
