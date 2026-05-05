# Synergy ERP - Full Stack MERN Application

A complete Enterprise Resource Planning system built with React, Express, MongoDB, and Node.js with real API integration, JWT authentication, and CRUD operations for multiple modules.

## Table of Contents
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Environment Variables](#environment-variables)
- [Authentication](#authentication)
- [Frontend Integration](#frontend-integration)
- [Data Models](#data-models)

## Project Structure

```
├── src/                              # React frontend
│   ├── api/
│   │   ├── client.js                # Axios client with interceptors
│   │   ├── endpoints.js             # All API endpoint constants
│   │   └── index.js
│   ├── context/
│   │   └── AuthContext.jsx          # Global auth state & JWT handling
│   ├── pages/
│   │   ├── auth/
│   │   │   ├── Login.jsx            # Login page
│   │   │   ├── Register.jsx         # Register page
│   │   │   └── Auth.module.css
│   │   ├── Dashboardpage.jsx
│   │   ├── Finance.jsx
│   │   ├── CreateInvoicePage.jsx    # Create invoice with backend
│   │   ├── InvoicesManagement.jsx
│   │   ├── HRPage.jsx
│   │   ├── SalesPage.jsx
│   │   ├── InventoryPage.jsx
│   │   ├── SupportPage.jsx
│   │   └── DesignSystemPage.jsx
│   ├── routes/
│   │   └── ProtectedRoute.jsx       # Auth-protected routes
│   ├── services/
│   ├── utils/
│   │   ├── financeService.js        # Finance API service
│   │   ├── employeeService.js       # Employee CRUD service
│   │   ├── productService.js        # Product CRUD service
│   │   ├── leadService.js           # Lead CRUD service
│   │   ├── invoicesService.js       # Invoice CRUD service
│   │   └── formatters.js
│   ├── App.jsx                       # Main app with AuthProvider
│   ├── main.jsx
│   └── index.css
│
├── backend/
│   ├── v1/
│   │   ├── config/
│   │   │   └── index.js             # Env variables config
│   │   ├── controllers/
│   │   │   ├── auth.js              # Auth logic (register/login/logout/me)
│   │   │   ├── employee.controller.js
│   │   │   ├── product.controller.js
│   │   │   ├── invoice.controller.js
│   │   │   └── lead.controller.js
│   │   ├── models/
│   │   │   ├── User.js              # Auth user model
│   │   │   ├── Employee.js
│   │   │   ├── Product.js
│   │   │   ├── Invoice.js
│   │   │   ├── Lead.js
│   │   │   └── Black-List.js        # Token blacklist for logout
│   │   ├── routes/
│   │   │   ├── index.js             # Main router
│   │   │   ├── auth.js              # Auth endpoints
│   │   │   ├── employee.routes.js
│   │   │   ├── product.routes.js
│   │   │   ├── invoice.routes.js
│   │   │   └── lead.routes.js
│   │   ├── middleware/
│   │   │   ├── verify.js            # JWT verification
│   │   │   ├── errorHandler.js      # Global error handler
│   │   │   ├── notFound.js          # 404 handler
│   │   │   ├── validateRequest.js
│   │   │   └── validators/ (employee, product, invoice, lead)
│   │   ├── utils/
│   │   │   ├── response.js          # Consistent response format
│   │   │   ├── AppError.js          # Custom error class
│   │   │   └── asyncHandler.js
│   │   └── server.js                # Express server setup
│   ├── server.js                     # Main entry point
│   ├── package.json
│   ├── .env                          # Backend environment variables
│   └── .env.example
│
├── package.json                      # Frontend dependencies
├── vite.config.js
├── eslint.config.js
└── README.md
```

## Setup Instructions

### Prerequisites
- Node.js (v16 or higher)
- npm or yarn
- MongoDB Atlas account (or local MongoDB)
- Git

### Backend Setup

1. **Navigate to backend directory:**
   ```bash
   cd backend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Create `.env` file with MongoDB credentials:**
   ```bash
   cp .env.example .env
   ```

4. **Edit `.env` with your values:**
   ```env
   PORT=5000
   FRONTEND_URL=http://localhost:5173
   URI=mongodb+srv://username:password@cluster.mongodb.net/synergy
   SECRET_ACCESS_TOKEN=your_secret_key_min_32_chars_long
   NODE_ENV=development
   ```

### Frontend Setup

1. **Navigate to root directory:**
   ```bash
   cd ..
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Create `.env` file (or use existing):**
   ```bash
   # .env already should exist, verify it contains:
   VITE_API_URL=http://localhost:5000/v1
   ```

## Running the Application

### Start Backend Server

```bash
cd backend
npm run dev
```

Server runs on: `http://localhost:5000`

### Start Frontend Development Server

```bash
# From root directory
npm run dev
```

Frontend runs on: `http://localhost:5173`

### Build for Production

**Frontend:**
```bash
npm run build
npm run preview
```

**Backend:**
Backend is ready to deploy as-is. Set `NODE_ENV=production` in `.env`

## API Endpoints

All endpoints require authentication (JWT token in httpOnly cookie) except Auth endpoints.

### Authentication Endpoints
- `POST /v1/auth/register` - Register new user
- `POST /v1/auth/login` - Login user
- `POST /v1/auth/logout` - Logout user (blacklist token)
- `GET /v1/auth/me` - Get current user (protected)

### Employee Endpoints (Protected)
- `GET /v1/employees` - Get all employees
- `POST /v1/employees` - Create employee
- `GET /v1/employees/:id` - Get employee by ID
- `PATCH /v1/employees/:id` - Update employee
- `DELETE /v1/employees/:id` - Delete employee

### Product Endpoints (Protected)
- `GET /v1/products` - Get all products
- `POST /v1/products` - Create product
- `GET /v1/products/:id` - Get product by ID
- `PATCH /v1/products/:id` - Update product
- `DELETE /v1/products/:id` - Delete product

### Invoice Endpoints (Protected)
- `GET /v1/invoices` - Get all invoices
- `POST /v1/invoices` - Create invoice
- `GET /v1/invoices/:id` - Get invoice by ID
- `PATCH /v1/invoices/:id` - Update invoice
- `DELETE /v1/invoices/:id` - Delete invoice

### Lead Endpoints (Protected)
- `GET /v1/leads` - Get all leads
- `POST /v1/leads` - Create lead
- `GET /v1/leads/:id` - Get lead by ID
- `PATCH /v1/leads/:id` - Update lead
- `DELETE /v1/leads/:id` - Delete lead

## Environment Variables

### Backend (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `PORT` | Server port | `5000` |
| `FRONTEND_URL` | Frontend URL for CORS | `http://localhost:5173` |
| `URI` | MongoDB connection string | `mongodb+srv://user:pass@cluster.mongodb.net/db` |
| `SECRET_ACCESS_TOKEN` | JWT signing secret | `your_secret_key` |
| `NODE_ENV` | Environment | `development` or `production` |

### Frontend (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API base URL | `http://localhost:5000/v1` |

## Authentication

The application uses **JWT tokens stored in httpOnly cookies** for security.

### Flow:
1. User registers → JWT token created → Stored in httpOnly cookie
2. User logs in → JWT token created → Stored in httpOnly cookie
3. Every API request → Cookie automatically included (withCredentials: true)
4. Backend verifies JWT → Request proceeds if valid
5. Token expires → User redirected to login

### Session Duration:
- JWT tokens expire after **20 minutes**
- Expired tokens added to blacklist (logout)

## Frontend Integration

### API Client Setup
The Axios client (`src/api/client.js`) is configured with:
- Base URL from environment variable
- Credentials enabled (withCredentials: true)
- Response interceptors for error handling
- Auto-redirect to login on 401 Unauthorized

### Using APIs in Components
```javascript
import invoicesService from "@/utils/invoicesService";

// Fetch invoices
const { data, error } = await invoicesService.fetchInvoices();

// Create invoice
const result = await invoicesService.createInvoice(invoiceData);

// Update invoice
const result = await invoicesService.updateInvoice(id, updatedData);

// Delete invoice
await invoicesService.deleteInvoice(id);
```

### Protected Routes
Protected pages redirect unauthenticated users to `/login`:
```javascript
<Routes>
  <Route path="/login" element={<Login />} />
  <Route path="/register" element={<Register />} />
  <Route element={<ProtectedRoute />}>
    <Route path="/dashboard" element={<Dashboard />} />
    {/* other protected routes */}
  </Route>
</Routes>
```

## Data Models

### User Model
```javascript
{
  first_name: String (required),
  last_name: String (required),
  email: String (required, unique),
  password: String (hashed, required),
  role: String (default: "0x01"),
  createdAt: Date,
  updatedAt: Date
}
```

### Employee Model
```javascript
{
  fullName: String (required),
  department: String (required),
  jobTitle: String (required),
  location: String (required),
  workEmail: String (required, unique),
  createdAt: Date,
  updatedAt: Date
}
```

### Product Model
```javascript
{
  productName: String (required),
  sku: String (required, unique),
  category: String (required),
  location: String (required),
  initialStatus: String (enum: ["In Stock", "Out of Stock", "Pending"]),
  unitCount: Number (required),
  lowStockThreshold: Number (required),
  createdAt: Date,
  updatedAt: Date
}
```

### Invoice Model
```javascript
{
  clientInformation: {
    customerName: String (required),
    billingEmail: String (required, email),
    billingAddress: String (required)
  },
  invoiceTimeline: {
    issueDate: Date (required),
    dueDate: Date (required),
    poNumber: String,
    currency: String (required)
  },
  lineItems: [{
    description: String (required),
    quantity: Number (required),
    unitPrice: Number (required),
    total: Number (required)
  }],
  taxConfiguration: {
    customTaxRate: Number
  },
  discountAndNotes: {
    discountAmountUSD: Number,
    internalNotes: String
  },
  createdAt: Date,
  updatedAt: Date
}
```

### Lead Model
```javascript
{
  companyName: String (required),
  dealValue: Number (required),
  priority: String (enum: ["Low", "Medium", "High"]),
  stage: String (enum: ["New", "Contacted", "Qualified", "Proposal", "Closed Won", "Closed Lost"]),
  createdAt: Date,
  updatedAt: Date
}
```

## Response Format

All API responses follow a consistent format:

### Success Response
```json
{
  "status": "success",
  "data": [{ /* resource data */ }],
  "message": "Success message"
}
```

### Error Response
```json
{
  "status": "failed",
  "data": [],
  "message": "Error message"
}
```

## Troubleshooting

### Issue: "Cannot GET /v1/auth/me"
- **Solution:** Ensure `Verify` middleware is applied to protected routes
- **Check:** `backend/v1/routes/index.js` - verify `Verify` middleware is used

### Issue: CORS errors
- **Solution:** Update `FRONTEND_URL` in backend `.env` to match your frontend URL
- **Default:** `http://localhost:5173` (Vite dev server)

### Issue: "Invalid token" errors
- **Solution:** Ensure `SECRET_ACCESS_TOKEN` is the same in backend `.env`
- **Note:** Changing the secret invalidates all existing tokens

### Issue: MongoDB connection fails
- **Solution:** Check `URI` in `.env` - verify connection string format and credentials
- **Format:** `mongodb+srv://username:password@cluster.mongodb.net/database_name`

## Performance Tips

1. **Enable connection pooling** in MongoDB Atlas
2. **Use pagination** for large datasets (implement in services)
3. **Cache frequently accessed data** (consider Redis)
4. **Compress responses** (gzip enabled by default in Express)
5. **Database indexing** - Already set on unique fields (email, sku)

## Security Best Practices

✅ **Implemented:**
- JWT tokens in httpOnly cookies (secure, not accessible to JS)
- CORS configured with credentials
- Password hashing with bcrypt
- Token blacklist for logout
- Input validation with express-validator
- Environment variables for secrets

⚠️ **For Production:**
- Set `FRONTEND_URL` to production domain only
- Set `COOKIE_SECURE=true` (requires HTTPS)
- Use strong `SECRET_ACCESS_TOKEN` (minimum 32 characters)
- Enable HTTPS on frontend and backend
- Set up rate limiting
- Use MongoDB Atlas IP whitelist

## License
ISC

## Support
For issues or questions, please contact the development team.
