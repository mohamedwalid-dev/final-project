# Prime ERP API Documentation

Beginner-friendly reference for testing the backend API with Postman or Thunder Client.

## Quick Start

Base URL:

```text
http://localhost:5005/v1
```

Recommended Postman/Thunder variables:

```text
baseUrl = http://localhost:5005/v1
token = paste_token_from_login_response_here
```

Default headers for JSON requests:

```http
Content-Type: application/json
Authorization: Bearer {{token}}
```

Authentication:

- `POST /auth/register` and `POST /auth/login` return a JWT token.
- Protected routes accept either `Authorization: Bearer <token>` or the `SessionID` cookie.
- Most business routes are protected. Inventory routes are currently public in the router.

Common success response shape:

```json
{
  "status": "success",
  "data": [],
  "message": "Success"
}
```

Some controllers also return:

```json
{
  "success": true,
  "data": {}
}
```

## Valid Values

User roles:

```text
client, support, accountant, hr, sales, manager, admin
```

User departments:

```text
client, support, finance, accounting, hr, sales, management, admin
```

Ticket priorities:

```text
urgent, high, medium, low
```

Ticket statuses:

```text
open, pending, resolved, closed
```

Ticket categories:

```text
invoice, payment, hr, technical, sales, general
```

Lead priorities:

```text
Low, Medium, High
```

Lead stages:

```text
New, Contacted, Qualified, Proposal, Closed Won, Closed Lost
```

Invoice statuses:

```text
Paid, Pending, Overdue
```

Invoice currencies:

```text
USD, EGP, SAR
```

Inventory categories:

```text
Electronics, Consumables, Hardware, Software, Components
```

Inventory locations:

```text
Warehouse A-12, Warehouse A-10, Warehouse B-04, Central Hub, Secure Vault
```

Inventory statuses:

```text
Healthy, Warning, Critical, Low, Out
```

## Endpoint Summary

| Area | Method | Endpoint | Auth |
|---|---:|---|---|
| Health | GET | `/v1` | No |
| Auth | POST | `/v1/auth/register` | No |
| Auth | POST | `/v1/auth/login` | No |
| Auth | POST | `/v1/auth/logout` | Optional token/cookie |
| Auth | GET | `/v1/auth/logout` | Optional token/cookie |
| Auth | GET | `/v1/auth/me` | Yes |
| Users | GET | `/v1/auth/users` | Yes |
| Users | GET | `/v1/auth/users/internal` | Yes |
| Users | GET | `/v1/auth/users/role/:role` | Yes |
| Users | GET | `/v1/auth/users/department/:department` | Yes |
| Employees | POST | `/v1/employees` | Yes |
| Employees | GET | `/v1/employees` | Yes |
| Employees | GET | `/v1/employees/:id` | Yes |
| Employees | PUT | `/v1/employees/:id` | Yes |
| Employees | PATCH | `/v1/employees/:id` | Yes |
| Employees | DELETE | `/v1/employees/:id` | Yes |
| Leads | POST | `/v1/leads` | Yes |
| Leads | GET | `/v1/leads` | Yes |
| Leads | GET | `/v1/leads/:id` | Yes |
| Leads | PUT | `/v1/leads/:id` | Yes |
| Leads | PATCH | `/v1/leads/:id` | Yes |
| Leads | DELETE | `/v1/leads/:id` | Yes |
| Invoices | POST | `/v1/invoices` | Yes |
| Invoices | GET | `/v1/invoices` | Yes |
| Invoices | GET | `/v1/invoices/:id` | Yes |
| Invoices | PUT | `/v1/invoices/:id` | Yes |
| Invoices | PATCH | `/v1/invoices/:id` | Yes |
| Invoices | DELETE | `/v1/invoices/:id` | Yes |
| Tickets | POST | `/v1/tickets` | Yes |
| Tickets | GET | `/v1/tickets` | Yes |
| Tickets | GET | `/v1/tickets/:id` | Yes |
| Tickets | POST | `/v1/tickets/:id/messages` | Yes |
| Tickets | PATCH | `/v1/tickets/:id/status` | Yes |
| Tickets | PATCH | `/v1/tickets/:id/assign` | Yes |
| Tickets | PATCH | `/v1/tickets/:id/department` | Yes |
| Internal Chats | GET | `/v1/chats` | Yes |
| Internal Chats | GET | `/v1/chats/ticket/:ticketId` | Yes |
| Internal Chats | GET | `/v1/chats/:id` | Yes |
| Internal Chats | POST | `/v1/chats/internal` | Yes |
| Internal Chats | POST | `/v1/chats/:id/messages` | Yes |
| Internal Chats | PATCH | `/v1/chats/:id/participants` | Yes |
| Internal Chats | PATCH | `/v1/chats/:id/close` | Yes |
| Support Chats | GET | `/v1/support-chats/me` | Yes |
| Support Chats | POST | `/v1/support-chats/me/messages` | Yes |
| Support Chats | GET | `/v1/support-chats` | Yes, support/admin |
| Support Chats | GET | `/v1/support-chats/:id` | Yes |
| Support Chats | POST | `/v1/support-chats/:id/reply` | Yes, support/admin |
| Support Chats | PATCH | `/v1/support-chats/:id/read` | Yes |
| Support Chats | PATCH | `/v1/support-chats/:id/close` | Yes, support/admin |
| Support Chats | PATCH | `/v1/support-chats/:id/reopen` | Yes, support/admin |
| Inventory | GET | `/v1/inventory/stats` | No |
| Inventory | GET | `/v1/inventory` | No |
| Inventory | POST | `/v1/inventory` | No |
| Inventory | GET | `/v1/inventory/:id` | No |
| Inventory | PUT | `/v1/inventory/:id` | No |
| Inventory | DELETE | `/v1/inventory/:id` | No |
| User Test | GET | `/v1/user` | Yes |
| Admin Test | GET | `/v1/admin` | Yes, admin |

## Health

### GET `/v1`

Checks that the API is running.

Response:

```json
{
  "status": "success",
  "data": [],
  "message": "Welcome to our API homepage!"
}
```

## Auth

### POST `/auth/register`

Creates a new user and returns a JWT.

Auth: not required

Required:

- `email`
- `password` minimum 8 characters

Optional:

- `name`
- `first_name`
- `last_name`
- `role`
- `department`
- `isActive`

Body:

```json
{
  "name": "Finance User",
  "email": "finance@example.com",
  "password": "password123",
  "role": "accountant",
  "department": "finance"
}
```

Response includes:

```json
{
  "token": "jwt_token_here",
  "user": {
    "_id": "user_id",
    "email": "finance@example.com",
    "role": "accountant",
    "department": "finance"
  }
}
```

### POST `/auth/login`

Logs in and returns a JWT.

Auth: not required

Body:

```json
{
  "email": "finance@example.com",
  "password": "password123"
}
```

Save the returned `token` into your Postman `token` variable.

### POST `/auth/logout`

Logs out by blacklisting the current token and clearing the auth cookie.

Auth: optional, but pass the token/cookie if you want to invalidate it.

Body: none

### GET `/auth/logout`

Same behavior as `POST /auth/logout`.

### GET `/auth/me`

Returns the authenticated user.

Auth: required

### GET `/auth/users`

Returns all users.

Auth: required

### GET `/auth/users/internal`

Returns active non-client users.

Auth: required

### GET `/auth/users/role/:role`

Returns active users with a role.

Auth: required

Example:

```http
GET {{baseUrl}}/auth/users/role/support
```

### GET `/auth/users/department/:department`

Returns active users in a department.

Auth: required

Example:

```http
GET {{baseUrl}}/auth/users/department/finance
```

## Employees

All employee endpoints require authentication.

Employee fields:

- `fullName` required
- `department` required
- `jobTitle` required
- `location` required
- `workEmail` required, unique, valid email

### POST `/employees`

Creates an employee.

Body:

```json
{
  "fullName": "Mona Ahmed",
  "department": "Finance",
  "jobTitle": "Accountant",
  "location": "Cairo",
  "workEmail": "mona.ahmed@example.com"
}
```

### GET `/employees`

Returns all employees.

### GET `/employees/:id`

Returns one employee by MongoDB ObjectId.

### PUT `/employees/:id`

Updates an employee. Use this when sending the full employee object.

Body:

```json
{
  "fullName": "Mona Ahmed",
  "department": "Finance",
  "jobTitle": "Senior Accountant",
  "location": "Cairo",
  "workEmail": "mona.ahmed@example.com"
}
```

### PATCH `/employees/:id`

Partially updates an employee.

Body:

```json
{
  "jobTitle": "Senior Accountant"
}
```

### DELETE `/employees/:id`

Deletes an employee.

## Leads

All lead endpoints require authentication.

Lead fields:

- `companyName` required
- `dealValue` required, number >= 0
- `priority` required: `Low`, `Medium`, `High`
- `stage` required: `New`, `Contacted`, `Qualified`, `Proposal`, `Closed Won`, `Closed Lost`

### POST `/leads`

Creates a lead.

Body:

```json
{
  "companyName": "Acme Corp",
  "dealValue": 15000,
  "priority": "High",
  "stage": "New"
}
```

### GET `/leads`

Returns all leads.

### GET `/leads/:id`

Returns one lead.

### PUT `/leads/:id`

Updates a lead. The validator expects all lead fields.

Body:

```json
{
  "companyName": "Acme Corp",
  "dealValue": 20000,
  "priority": "Medium",
  "stage": "Proposal"
}
```

### PATCH `/leads/:id`

Updates a lead. Current validator expects the same fields as create.

Body:

```json
{
  "companyName": "Acme Corp",
  "dealValue": 20000,
  "priority": "Medium",
  "stage": "Proposal"
}
```

### DELETE `/leads/:id`

Deletes a lead.

## Invoices

All invoice endpoints require authentication.

Invoice fields:

- `status`: optional, `Paid`, `Pending`, `Overdue`
- `clientInformation.customerName` required
- `clientInformation.billingEmail` required
- `clientInformation.billingAddress` required
- `invoiceTimeline.issueDate` required ISO date
- `invoiceTimeline.dueDate` required ISO date
- `invoiceTimeline.currency` required: `USD`, `EGP`, `SAR`
- `lineItems` required, at least one item
- `lineItems[].description` required
- `lineItems[].quantity` required, integer >= 1
- `lineItems[].unitPrice` required, number >= 0
- `lineItems[].total` required, number >= 0
- `taxConfiguration.customTaxRate` optional, 0 to 100
- `discountAndNotes.discountAmountUSD` optional, >= 0
- `discountAndNotes.internalNotes` optional

### POST `/invoices`

Creates an invoice.

Body:

```json
{
  "status": "Pending",
  "clientInformation": {
    "customerName": "Acme Corp",
    "billingEmail": "billing@acme.com",
    "billingAddress": "123 Business Street"
  },
  "invoiceTimeline": {
    "issueDate": "2026-05-23",
    "dueDate": "2026-06-23",
    "poNumber": "PO-1001",
    "currency": "USD"
  },
  "lineItems": [
    {
      "description": "ERP subscription",
      "quantity": 2,
      "unitPrice": 500,
      "total": 1000
    }
  ],
  "taxConfiguration": {
    "customTaxRate": 14
  },
  "discountAndNotes": {
    "discountAmountUSD": 50,
    "internalNotes": "Annual customer"
  }
}
```

### GET `/invoices`

Returns all invoices.

### GET `/invoices/:id`

Returns one invoice.

### PUT `/invoices/:id`

Updates an invoice. The validator expects the full invoice shape.

### PATCH `/invoices/:id`

Partially updates an invoice.

Body:

```json
{
  "status": "Paid"
}
```

### DELETE `/invoices/:id`

Deletes an invoice.

## Tickets

All ticket endpoints require authentication.

Important behavior:

- Support/admin users can create and manage tickets.
- Department users see tickets where `relatedDepartment` equals their department.
- `Ticket.messages` is for client/support/system messages only.
- Internal department messages are stored in `Chat.messages` under `/chats`.

### POST `/tickets`

Creates a ticket. Also creates or links an internal department chat for the ticket.

Auth: support/admin

Required:

- `clientName`
- `clientEmail`
- `subject`
- `description`

Optional:

- `clientId`
- `priority`
- `category`
- `relatedDepartment`
- `attachments`

Body:

```json
{
  "clientName": "Client One",
  "clientEmail": "client@example.com",
  "subject": "Payment confirmation needed",
  "description": "Client says payment was sent but invoice is still pending.",
  "priority": "high",
  "category": "payment",
  "relatedDepartment": "finance",
  "attachments": []
}
```

### GET `/tickets`

Returns tickets visible to the authenticated user.

Auth behavior:

- Support/admin: all tickets
- Other internal users: only tickets where `relatedDepartment` equals their department

### GET `/tickets/:id`

Returns one ticket if the user has access.

### POST `/tickets/:id/messages`

Adds a customer-facing ticket message.

Use this for client/support/system messages only. Do not use this endpoint for internal department replies.

Body:

```json
{
  "text": "We are checking this with the finance team.",
  "senderType": "support",
  "attachments": []
}
```

### PATCH `/tickets/:id/status`

Updates ticket status.

Auth: support/admin

Body:

```json
{
  "status": "pending"
}
```

### PATCH `/tickets/:id/assign`

Assigns a ticket to a support agent.

Auth: support/admin

Body:

```json
{
  "agentId": "USER_OBJECT_ID"
}
```

### PATCH `/tickets/:id/department`

Changes the related department and updates linked internal chats.

Auth: support/admin

Body:

```json
{
  "relatedDepartment": "finance"
}
```

## Internal Ticket Chats

All internal chat endpoints require authentication.

Important:

- Clients cannot access internal chats.
- Internal ticket chat messages are stored in `Chat.messages`.
- Message sender identity is taken from the authenticated user.
- The backend only expects `text` and optional `attachments` when sending a message.

### GET `/chats`

Returns internal chats visible to the authenticated user.

### GET `/chats/ticket/:ticketId`

Returns internal chats linked to a ticket.

Example:

```http
GET {{baseUrl}}/chats/ticket/665f00000000000000000001
```

### GET `/chats/:id`

Returns one internal chat.

### POST `/chats/internal`

Creates or returns an internal department chat for a ticket.

Body:

```json
{
  "ticketId": "TICKET_OBJECT_ID",
  "requestedDepartment": "finance",
  "requestedRole": "accountant",
  "title": "Payment confirmation needed",
  "priority": "high",
  "summary": "Please verify the payment.",
  "participants": [],
  "text": "Please verify the payment for this client.",
  "attachments": []
}
```

Notes:

- If `requestedDepartment` is omitted, the ticket `relatedDepartment` is used.
- If `priority` is omitted, the ticket priority is used.
- If the chat already exists, the endpoint returns the existing chat.

### POST `/chats/:id/messages`

Adds a new internal chat message.

Body:

```json
{
  "text": "Finance has confirmed the payment.",
  "attachments": []
}
```

The server creates the saved message using the authenticated user:

```json
{
  "senderId": "authenticated_user_id",
  "senderRole": "accountant",
  "senderDepartment": "finance",
  "senderName": "Finance User",
  "text": "Finance has confirmed the payment.",
  "isInternalNote": true,
  "attachments": []
}
```

### PATCH `/chats/:id/participants`

Adds an internal participant to a chat.

Body:

```json
{
  "participantId": "USER_OBJECT_ID"
}
```

Alternative key:

```json
{
  "userId": "USER_OBJECT_ID"
}
```

### PATCH `/chats/:id/close`

Closes an internal chat.

Body: none

## Support Chats

These endpoints are for general user-to-support chat, separate from ticket internal chats.

All support chat endpoints require authentication.

### GET `/support-chats/me`

Gets or creates the authenticated user's support chat.

### POST `/support-chats/me/messages`

Sends a message from the authenticated user to support.

Body:

```json
{
  "text": "I need help with my account."
}
```

### GET `/support-chats`

Returns all support chats.

Auth: support/admin

### GET `/support-chats/:id`

Returns one support chat if the user has access.

### POST `/support-chats/:id/reply`

Sends a support/admin reply.

Auth: support/admin

Body:

```json
{
  "text": "Thanks for contacting support. We are checking this now."
}
```

### PATCH `/support-chats/:id/read`

Marks messages as read for the authenticated user/support side.

Body:

```json
{}
```

### PATCH `/support-chats/:id/close`

Closes a support chat.

Auth: support/admin

Body:

```json
{}
```

### PATCH `/support-chats/:id/reopen`

Reopens a support chat.

Auth: support/admin

Body:

```json
{}
```

## Inventory

Inventory routes are mounted without the `Verify` middleware in the current router.

Inventory fields:

- `name` required
- `category` required
- `sku` required, unique, stored uppercase
- `location` required
- `units` required, number >= 0
- `threshold` required, number >= 0
- `stockPct` auto-calculated
- `status` auto-calculated

### GET `/inventory/stats`

Returns inventory summary stats.

### GET `/inventory`

Returns inventory products.

Query parameters:

- `search`: searches name, SKU, and location
- `status`: exact inventory status
- `category`: exact category
- `location`: exact location

Examples:

```http
GET {{baseUrl}}/inventory?search=laptop
GET {{baseUrl}}/inventory?status=Critical
GET {{baseUrl}}/inventory?category=Hardware&location=Central%20Hub
```

### POST `/inventory`

Creates a product.

Body:

```json
{
  "name": "Laptop Charger",
  "category": "Electronics",
  "sku": "LC-1001",
  "location": "Warehouse A-12",
  "units": 24,
  "threshold": 10
}
```

### GET `/inventory/:id`

Returns one product.

### PUT `/inventory/:id`

Updates a product.

Body:

```json
{
  "name": "Laptop Charger",
  "category": "Electronics",
  "sku": "LC-1001",
  "location": "Central Hub",
  "units": 18,
  "threshold": 10
}
```

### DELETE `/inventory/:id`

Deletes a product.

## Test Routes

### GET `/user`

Protected test route. Returns a welcome message if the token is valid.

Auth: required

### GET `/admin`

Protected admin test route.

Auth: admin role required

## Socket.IO Notes

Socket.IO is not a normal HTTP API request, but it is used for real-time chat updates.

Backend URL:

```text
http://localhost:5005
```

Internal ticket chat events:

```js
socket.emit("joinInternalChat", chatId);
socket.emit("leaveInternalChat", chatId);
socket.on("newInternalChatMessage", (payload) => {});
```

Payload emitted by backend:

```json
{
  "chatId": "CHAT_OBJECT_ID",
  "ticketId": "TICKET_OBJECT_ID",
  "message": {
    "_id": "MESSAGE_OBJECT_ID",
    "senderId": "USER_OBJECT_ID",
    "senderRole": "accountant",
    "senderDepartment": "finance",
    "senderName": "Finance User",
    "text": "Finance has confirmed the payment.",
    "isInternalNote": true,
    "attachments": [],
    "createdAt": "2026-05-23T00:00:00.000Z"
  }
}
```

Support chat events:

```js
socket.emit("join_support_chat", { chatId });
socket.emit("leave_support_chat", { chatId });
socket.on("support_chat_updated", (payload) => {});
socket.on("support_message_received", (payload) => {});
```

## Common Errors

### 401 Not authenticated

You did not pass a valid token or auth cookie.

Fix:

```http
Authorization: Bearer {{token}}
```

### 403 Forbidden

The user is logged in but does not have permission.

Examples:

- A client tries to open an internal department chat.
- A department user tries to update ticket status.
- A non-support user tries to list all support chats.

### 404 Not found

The requested document ID does not exist.

### 400 Validation error

The body is missing required fields or contains invalid enum values.

## Suggested Testing Flow

1. Register or log in as a support user.
2. Save the returned token.
3. Create a ticket with `relatedDepartment: "finance"`.
4. Log in as a finance/accountant user.
5. Call `GET /tickets` and confirm the ticket appears.
6. Call `GET /chats/ticket/:ticketId` to fetch the internal chat.
7. Call `POST /chats/:id/messages` to send an internal reply.
8. Confirm the message is saved under `Chat.messages`, not `Ticket.messages`.
