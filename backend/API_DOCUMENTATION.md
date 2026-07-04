# Prime API Documentation

## Overview

The Prime API is a comprehensive business management REST API built with Express.js and MongoDB. It provides endpoints for managing employees, leads, invoices, products, and user authentication.

**Version:** v1  
**Base URL:** `http://localhost:5000/v1` (or your configured port)  
**Authentication:** JWT-based cookie authentication  
**Database:** MongoDB

---

## Table of Contents

1. [Authentication](#authentication)
2. [Data Models](#data-models)
3. [Endpoints](#endpoints)
   - [Authentication Endpoints](#authentication-endpoints)
   - [Employee Endpoints](#employee-endpoints)
   - [Lead Endpoints](#lead-endpoints)
   - [Invoice Endpoints](#invoice-endpoints)
   - [Product Endpoints](#product-endpoints)
4. [Common Response Format](#common-response-format)
5. [Error Handling](#error-handling)
6. [Example Requests](#example-requests)
7. [Best Practices](#best-practices)

---

## Authentication

The API uses **JWT (JSON Web Token) based authentication** via HTTP-only cookies.

### Authentication Flow

1. **Register** - Create a new user account with email and password
2. **Login** - Authenticate user credentials and receive a JWT token in a cookie
3. **Protected Routes** - Include the cookie in subsequent requests
4. **Logout** - Invalidate the token by blacklisting it

### Headers

Protected routes require the `SessionID` cookie to be automatically sent by the browser.

**Cookie Details:**
- **Name:** `SessionID`
- **Expiration:** 20 minutes
- **HTTP-Only:** Yes (secure, inaccessible to JavaScript)
- **Secure:** Yes (HTTPS only)
- **SameSite:** None

### User Roles

- **User (0x01):** Default role for registered users
- **Admin (0x88):** Administrative access to protected admin endpoints

---

## Data Models

### User Model

```json
{
  "_id": "ObjectId",
  "first_name": "string (max 25)",
  "last_name": "string (max 25)",
  "email": "string (unique, lowercase)",
  "password": "string (hashed with bcrypt)",
  "role": "string (default: '0x01')",
  "createdAt": "ISO8601",
  "updatedAt": "ISO8601"
}
```

### Employee Model

```json
{
  "_id": "ObjectId",
  "fullName": "string (required, trimmed)",
  "department": "string (required, trimmed)",
  "jobTitle": "string (required, trimmed)",
  "location": "string (required, trimmed)",
  "workEmail": "string (required, unique, email format)",
  "createdAt": "ISO8601",
  "updatedAt": "ISO8601"
}
```

### Lead Model

```json
{
  "_id": "ObjectId",
  "companyName": "string (required, trimmed)",
  "dealValue": "number (required, >= 0)",
  "priority": "enum: 'Low' | 'Medium' | 'High'",
  "stage": "enum: 'New' | 'Contacted' | 'Qualified' | 'Proposal' | 'Closed Won' | 'Closed Lost'",
  "createdAt": "ISO8601",
  "updatedAt": "ISO8601"
}
```

### Invoice Model

```json
{
  "_id": "ObjectId",
  "clientInformation": {
    "customerName": "string (required)",
    "billingEmail": "string (required, email format)",
    "billingAddress": "string (required)"
  },
  "invoiceTimeline": {
    "issueDate": "ISO8601 (required)",
    "dueDate": "ISO8601 (required)",
    "poNumber": "string (optional, null by default)",
    "currency": "string (required, uppercase)"
  },
  "lineItems": [
    {
      "description": "string (required)",
      "quantity": "number (required, >= 1)",
      "unitPrice": "number (required, >= 0)",
      "total": "number (required, >= 0)"
    }
  ],
  "taxConfiguration": {
    "customTaxRate": "number (0-100, optional)"
  },
  "discountAndNotes": {
    "discountAmountUSD": "number (>= 0, optional)",
    "internalNotes": "string (optional)"
  },
  "createdAt": "ISO8601",
  "updatedAt": "ISO8601"
}
```

### Product Model

```json
{
  "_id": "ObjectId",
  "productName": "string (required, trimmed)",
  "sku": "string (required, unique, uppercase)",
  "category": "string (required, trimmed)",
  "location": "string (required, trimmed)",
  "initialStatus": "enum: 'In Stock' | 'Out of Stock' | 'Pending'",
  "unitCount": "number (required, >= 0)",
  "lowStockThreshold": "number (required, >= 0)",
  "createdAt": "ISO8601",
  "updatedAt": "ISO8601"
}
```

---

## Common Response Format

All API responses follow a consistent format:

### Success Response (2xx)

```json
{
  "status": "success",
  "data": [{}] or {},
  "message": "Operation completed successfully"
}
```

### Error Response (4xx, 5xx)

```json
{
  "status": "failed" or "error",
  "data": [] or null,
  "message": "Error description"
}
```

---

## Error Handling

| Status Code | Meaning |
|---|---|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 400 | Bad Request - Invalid input or validation error |
| 401 | Unauthorized - Authentication required or failed |
| 404 | Not Found - Resource not found |
| 500 | Internal Server Error - Server error |

---

## Endpoints

### Authentication Endpoints

#### Register User

**POST** `/v1/auth/register`

Creates a new user account.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "email": "john@example.com",
  "password": "SecurePassword123"
}
```

**Validation Rules:**
- `email`: Valid email format (normalized)
- `first_name`: Required, max 25 characters
- `last_name`: Required, max 25 characters
- `password`: Required, minimum 8 characters

**Success Response (200):**
```json
{
  "status": "success",
  "data": [
    {
      "_id": "507f1f77bcf86cd799439011",
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com",
      "createdAt": "2024-05-03T10:30:00Z",
      "updatedAt": "2024-05-03T10:30:00Z"
    }
  ],
  "message": "Thank you for registering with us. Your account has been successfully created."
}
```

**Error Response (400):**
```json
{
  "status": "failed",
  "data": [],
  "message": "It seems you already have an account, please log in instead."
}
```

---

#### Login User

**POST** `/v1/auth/login`

Authenticates user and returns JWT token as HTTP-only cookie.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "john@example.com",
  "password": "SecurePassword123"
}
```

**Validation Rules:**
- `email`: Valid email format
- `password`: Required

**Success Response (200):**
```json
{
  "status": "success",
  "message": "You have successfully logged in."
}
```

**Set-Cookie Header:**
```
SessionID=<jwt_token>; Max-Age=1200; HttpOnly; Secure; SameSite=None
```

**Error Response (401):**
```json
{
  "status": "failed",
  "data": [],
  "message": "Invalid email or password. Please try again with the correct credentials."
}
```

---

#### Logout User

**GET** `/v1/auth/logout`

Invalidates the user's session by blacklisting the token.

**Headers:**
```
Cookie: SessionID=<jwt_token>
```

**Success Response (200):**
```json
{
  "message": "You are logged out!"
}
```

**Clear-Site-Data Header:**
```
Clear-Site-Data: "cookies"
```

---

### Employee Endpoints

#### Create Employee

**POST** `/v1/employees`

Creates a new employee record.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "fullName": "Alice Johnson",
  "department": "Engineering",
  "jobTitle": "Senior Developer",
  "location": "San Francisco, CA",
  "workEmail": "alice.johnson@company.com"
}
```

**Validation Rules:**
- `fullName`: Required
- `department`: Required
- `jobTitle`: Required
- `location`: Required
- `workEmail`: Required, valid email format, unique

**Success Response (201):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439012",
    "fullName": "Alice Johnson",
    "department": "Engineering",
    "jobTitle": "Senior Developer",
    "location": "San Francisco, CA",
    "workEmail": "alice.johnson@company.com",
    "createdAt": "2024-05-03T10:35:00Z",
    "updatedAt": "2024-05-03T10:35:00Z"
  },
  "message": "Employee created successfully"
}
```

---

#### Get All Employees

**GET** `/v1/employees`

Retrieves all employees, sorted by creation date (newest first).

**Success Response (200):**
```json
{
  "status": "success",
  "data": [
    {
      "_id": "507f1f77bcf86cd799439012",
      "fullName": "Alice Johnson",
      "department": "Engineering",
      "jobTitle": "Senior Developer",
      "location": "San Francisco, CA",
      "workEmail": "alice.johnson@company.com",
      "createdAt": "2024-05-03T10:35:00Z",
      "updatedAt": "2024-05-03T10:35:00Z"
    }
  ],
  "message": "Employees fetched successfully"
}
```

---

#### Get Employee by ID

**GET** `/v1/employees/:id`

Retrieves a specific employee by ID.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the employee

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439012",
    "fullName": "Alice Johnson",
    "department": "Engineering",
    "jobTitle": "Senior Developer",
    "location": "San Francisco, CA",
    "workEmail": "alice.johnson@company.com",
    "createdAt": "2024-05-03T10:35:00Z",
    "updatedAt": "2024-05-03T10:35:00Z"
  },
  "message": "Employee fetched successfully"
}
```

**Error Response (404):**
```json
{
  "status": "failed",
  "data": [],
  "message": "Employee not found"
}
```

---

#### Update Employee

**PUT** `/v1/employees/:id`

Updates an employee's information.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the employee

**Request Body (all fields optional):**
```json
{
  "fullName": "Alice Smith",
  "department": "Product",
  "jobTitle": "Lead Developer",
  "location": "New York, NY",
  "workEmail": "alice.smith@company.com"
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439012",
    "fullName": "Alice Smith",
    "department": "Product",
    "jobTitle": "Lead Developer",
    "location": "New York, NY",
    "workEmail": "alice.smith@company.com",
    "createdAt": "2024-05-03T10:35:00Z",
    "updatedAt": "2024-05-03T11:00:00Z"
  },
  "message": "Employee updated successfully"
}
```

---

#### Delete Employee

**DELETE** `/v1/employees/:id`

Deletes an employee record.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the employee

**Success Response (200):**
```json
{
  "status": "success",
  "data": [],
  "message": "Employee deleted successfully"
}
```

---

### Lead Endpoints

#### Create Lead

**POST** `/v1/leads`

Creates a new sales lead.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "companyName": "TechCorp Inc",
  "dealValue": 50000,
  "priority": "High",
  "stage": "Proposal"
}
```

**Validation Rules:**
- `companyName`: Required, string
- `dealValue`: Required, numeric, >= 0
- `priority`: Required, enum: "Low", "Medium", "High"
- `stage`: Required, enum: "New", "Contacted", "Qualified", "Proposal", "Closed Won", "Closed Lost"

**Success Response (201):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439013",
    "companyName": "TechCorp Inc",
    "dealValue": 50000,
    "priority": "High",
    "stage": "Proposal",
    "createdAt": "2024-05-03T10:40:00Z",
    "updatedAt": "2024-05-03T10:40:00Z"
  },
  "message": "Lead created successfully"
}
```

---

#### Get All Leads

**GET** `/v1/leads`

Retrieves all leads, sorted by creation date (newest first).

**Success Response (200):**
```json
{
  "status": "success",
  "data": [
    {
      "_id": "507f1f77bcf86cd799439013",
      "companyName": "TechCorp Inc",
      "dealValue": 50000,
      "priority": "High",
      "stage": "Proposal",
      "createdAt": "2024-05-03T10:40:00Z",
      "updatedAt": "2024-05-03T10:40:00Z"
    }
  ],
  "message": "Leads fetched successfully"
}
```

---

#### Get Lead by ID

**GET** `/v1/leads/:id`

Retrieves a specific lead by ID.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the lead

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439013",
    "companyName": "TechCorp Inc",
    "dealValue": 50000,
    "priority": "High",
    "stage": "Proposal",
    "createdAt": "2024-05-03T10:40:00Z",
    "updatedAt": "2024-05-03T10:40:00Z"
  },
  "message": "Lead fetched successfully"
}
```

**Error Response (404):**
```json
{
  "status": "failed",
  "data": [],
  "message": "Lead not found"
}
```

---

#### Update Lead

**PUT** `/v1/leads/:id`

Updates a lead's information.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the lead

**Request Body (all fields optional):**
```json
{
  "companyName": "TechCorp Solutions",
  "dealValue": 75000,
  "priority": "Medium",
  "stage": "Closed Won"
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439013",
    "companyName": "TechCorp Solutions",
    "dealValue": 75000,
    "priority": "Medium",
    "stage": "Closed Won",
    "createdAt": "2024-05-03T10:40:00Z",
    "updatedAt": "2024-05-03T11:05:00Z"
  },
  "message": "Lead updated successfully"
}
```

---

#### Delete Lead

**DELETE** `/v1/leads/:id`

Deletes a lead record.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the lead

**Success Response (200):**
```json
{
  "status": "success",
  "data": [],
  "message": "Lead deleted successfully"
}
```

---

### Invoice Endpoints

#### Create Invoice

**POST** `/v1/invoices`

Creates a new invoice with line items.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "clientInformation": {
    "customerName": "ABC Corporation",
    "billingEmail": "billing@abccorp.com",
    "billingAddress": "123 Business Ave, Suite 100, New York, NY 10001"
  },
  "invoiceTimeline": {
    "issueDate": "2024-05-03T00:00:00Z",
    "dueDate": "2024-06-03T00:00:00Z",
    "poNumber": "PO-2024-001",
    "currency": "USD"
  },
  "lineItems": [
    {
      "description": "Web Development Services",
      "quantity": 40,
      "unitPrice": 150,
      "total": 6000
    },
    {
      "description": "UI/UX Design",
      "quantity": 20,
      "unitPrice": 100,
      "total": 2000
    }
  ],
  "taxConfiguration": {
    "customTaxRate": 10
  },
  "discountAndNotes": {
    "discountAmountUSD": 500,
    "internalNotes": "Early payment discount applied"
  }
}
```

**Validation Rules:**
- `clientInformation.customerName`: Required, string
- `clientInformation.billingEmail`: Required, valid email format
- `clientInformation.billingAddress`: Required, string
- `invoiceTimeline.issueDate`: Required, ISO8601 date
- `invoiceTimeline.dueDate`: Required, ISO8601 date
- `invoiceTimeline.currency`: Required, string
- `lineItems`: Required, array with minimum 1 item
- `lineItems[].description`: Required
- `lineItems[].quantity`: Required, integer >= 1
- `lineItems[].unitPrice`: Required, number >= 0
- `lineItems[].total`: Required, number >= 0
- `taxConfiguration.customTaxRate`: Optional, 0-100
- `discountAndNotes.discountAmountUSD`: Optional, >= 0

**Success Response (201):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439014",
    "clientInformation": {
      "customerName": "ABC Corporation",
      "billingEmail": "billing@abccorp.com",
      "billingAddress": "123 Business Ave, Suite 100, New York, NY 10001"
    },
    "invoiceTimeline": {
      "issueDate": "2024-05-03T00:00:00Z",
      "dueDate": "2024-06-03T00:00:00Z",
      "poNumber": "PO-2024-001",
      "currency": "USD"
    },
    "lineItems": [
      {
        "_id": "507f1f77bcf86cd799439015",
        "description": "Web Development Services",
        "quantity": 40,
        "unitPrice": 150,
        "total": 6000
      },
      {
        "_id": "507f1f77bcf86cd799439016",
        "description": "UI/UX Design",
        "quantity": 20,
        "unitPrice": 100,
        "total": 2000
      }
    ],
    "taxConfiguration": {
      "customTaxRate": 10
    },
    "discountAndNotes": {
      "discountAmountUSD": 500,
      "internalNotes": "Early payment discount applied"
    },
    "createdAt": "2024-05-03T10:45:00Z",
    "updatedAt": "2024-05-03T10:45:00Z"
  },
  "message": "Invoice created successfully"
}
```

---

#### Get All Invoices

**GET** `/v1/invoices`

Retrieves all invoices.

**Success Response (200):**
```json
{
  "status": "success",
  "data": [
    {
      "_id": "507f1f77bcf86cd799439014",
      "clientInformation": {...},
      "invoiceTimeline": {...},
      "lineItems": [...],
      "taxConfiguration": {...},
      "discountAndNotes": {...},
      "createdAt": "2024-05-03T10:45:00Z",
      "updatedAt": "2024-05-03T10:45:00Z"
    }
  ],
  "message": "Invoices fetched successfully"
}
```

---

#### Get Invoice by ID

**GET** `/v1/invoices/:id`

Retrieves a specific invoice by ID.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the invoice

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439014",
    "clientInformation": {...},
    "invoiceTimeline": {...},
    "lineItems": [...],
    "taxConfiguration": {...},
    "discountAndNotes": {...},
    "createdAt": "2024-05-03T10:45:00Z",
    "updatedAt": "2024-05-03T10:45:00Z"
  },
  "message": "Invoice fetched successfully"
}
```

**Error Response (404):**
```json
{
  "status": "failed",
  "data": null,
  "message": "Invoice not found"
}
```

---

#### Update Invoice

**PUT** `/v1/invoices/:id`

Updates an invoice's information.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the invoice

**Request Body (all fields optional):**
```json
{
  "clientInformation": {
    "customerName": "ABC Corporation Ltd"
  },
  "invoiceTimeline": {
    "dueDate": "2024-06-15T00:00:00Z"
  },
  "discountAndNotes": {
    "discountAmountUSD": 750
  }
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439014",
    "clientInformation": {...},
    "invoiceTimeline": {...},
    "lineItems": [...],
    "taxConfiguration": {...},
    "discountAndNotes": {...},
    "createdAt": "2024-05-03T10:45:00Z",
    "updatedAt": "2024-05-03T11:10:00Z"
  },
  "message": "Invoice updated successfully"
}
```

---

#### Delete Invoice

**DELETE** `/v1/invoices/:id`

Deletes an invoice record.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the invoice

**Success Response (200):**
```json
{
  "status": "success",
  "data": null,
  "message": "Invoice deleted successfully"
}
```

---

### Product Endpoints

#### Create Product

**POST** `/v1/products`

Creates a new product record.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "productName": "Laptop Pro 15",
  "sku": "LP15-2024",
  "category": "Electronics",
  "location": "Warehouse A",
  "initialStatus": "In Stock",
  "unitCount": 150,
  "lowStockThreshold": 20
}
```

**Validation Rules:**
- `productName`: Required
- `sku`: Required, unique, converted to uppercase
- `category`: Required
- `location`: Required
- `initialStatus`: Required, enum: "In Stock", "Out of Stock", "Pending"
- `unitCount`: Required, numeric
- `lowStockThreshold`: Required, numeric

**Success Response (201):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439017",
    "productName": "Laptop Pro 15",
    "sku": "LP15-2024",
    "category": "Electronics",
    "location": "Warehouse A",
    "initialStatus": "In Stock",
    "unitCount": 150,
    "lowStockThreshold": 20,
    "createdAt": "2024-05-03T10:50:00Z",
    "updatedAt": "2024-05-03T10:50:00Z"
  },
  "message": "Product created successfully"
}
```

---

#### Get All Products

**GET** `/v1/products`

Retrieves all products.

**Success Response (200):**
```json
{
  "status": "success",
  "data": [
    {
      "_id": "507f1f77bcf86cd799439017",
      "productName": "Laptop Pro 15",
      "sku": "LP15-2024",
      "category": "Electronics",
      "location": "Warehouse A",
      "initialStatus": "In Stock",
      "unitCount": 150,
      "lowStockThreshold": 20,
      "createdAt": "2024-05-03T10:50:00Z",
      "updatedAt": "2024-05-03T10:50:00Z"
    }
  ],
  "message": "Products fetched successfully"
}
```

---

#### Get Product by ID

**GET** `/v1/products/:id`

Retrieves a specific product by ID.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the product

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439017",
    "productName": "Laptop Pro 15",
    "sku": "LP15-2024",
    "category": "Electronics",
    "location": "Warehouse A",
    "initialStatus": "In Stock",
    "unitCount": 150,
    "lowStockThreshold": 20,
    "createdAt": "2024-05-03T10:50:00Z",
    "updatedAt": "2024-05-03T10:50:00Z"
  },
  "message": "Product fetched successfully"
}
```

**Error Response (404):**
```json
{
  "status": "failed",
  "data": [],
  "message": "Product not found"
}
```

---

#### Update Product

**PUT** `/v1/products/:id`

Updates a product's information.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the product

**Request Body (all fields optional):**
```json
{
  "unitCount": 120,
  "lowStockThreshold": 25,
  "initialStatus": "Out of Stock"
}
```

**Success Response (200):**
```json
{
  "status": "success",
  "data": {
    "_id": "507f1f77bcf86cd799439017",
    "productName": "Laptop Pro 15",
    "sku": "LP15-2024",
    "category": "Electronics",
    "location": "Warehouse A",
    "initialStatus": "Out of Stock",
    "unitCount": 120,
    "lowStockThreshold": 25,
    "createdAt": "2024-05-03T10:50:00Z",
    "updatedAt": "2024-05-03T11:15:00Z"
  },
  "message": "Product updated successfully"
}
```

---

#### Delete Product

**DELETE** `/v1/products/:id`

Deletes a product record.

**Path Parameters:**
- `id` (required): MongoDB ObjectId of the product

**Success Response (200):**
```json
{
  "status": "success",
  "data": [],
  "message": "Product deleted successfully"
}
```

---

### Protected Routes

#### Get User Dashboard

**GET** `/v1/user`

Returns a welcome message for authenticated users. Requires valid JWT cookie.

**Headers:**
```
Cookie: SessionID=<jwt_token>
```

**Success Response (200):**
```json
{
  "status": "success",
  "message": "Welcome to your Dashboard!"
}
```

**Error Response (401):**
```json
{
  "message": "This session has expired. Please login"
}
```

---

#### Get Admin Portal

**GET** `/v1/admin`

Returns a welcome message for admin users only. Requires valid JWT cookie with admin role (0x88).

**Headers:**
```
Cookie: SessionID=<jwt_token>
```

**Success Response (200):**
```json
{
  "status": "success",
  "message": "Welcome to the Admin portal!"
}
```

**Error Response (401):**
```json
{
  "status": "failed",
  "message": "You are not authorized to view this page."
}
```

---

## Example Requests

### Using cURL

#### Register

```bash
curl -X POST http://localhost:5000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "password": "SecurePassword123"
  }'
```

#### Login

```bash
curl -X POST http://localhost:5000/v1/auth/login \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{
    "email": "john@example.com",
    "password": "SecurePassword123"
  }'
```

#### Create Employee

```bash
curl -X POST http://localhost:5000/v1/employees \
  -H "Content-Type: application/json" \
  -d '{
    "fullName": "Alice Johnson",
    "department": "Engineering",
    "jobTitle": "Senior Developer",
    "location": "San Francisco, CA",
    "workEmail": "alice.johnson@company.com"
  }'
```

#### Get All Employees

```bash
curl -X GET http://localhost:5000/v1/employees
```

#### Create Lead

```bash
curl -X POST http://localhost:5000/v1/leads \
  -H "Content-Type: application/json" \
  -d '{
    "companyName": "TechCorp Inc",
    "dealValue": 50000,
    "priority": "High",
    "stage": "Proposal"
  }'
```

#### Create Invoice

```bash
curl -X POST http://localhost:5000/v1/invoices \
  -H "Content-Type: application/json" \
  -d '{
    "clientInformation": {
      "customerName": "ABC Corporation",
      "billingEmail": "billing@abccorp.com",
      "billingAddress": "123 Business Ave, New York, NY"
    },
    "invoiceTimeline": {
      "issueDate": "2024-05-03T00:00:00Z",
      "dueDate": "2024-06-03T00:00:00Z",
      "currency": "USD"
    },
    "lineItems": [
      {
        "description": "Consulting Services",
        "quantity": 10,
        "unitPrice": 500,
        "total": 5000
      }
    ]
  }'
```

#### Create Product

```bash
curl -X POST http://localhost:5000/v1/products \
  -H "Content-Type: application/json" \
  -d '{
    "productName": "Laptop Pro 15",
    "sku": "LP15-2024",
    "category": "Electronics",
    "location": "Warehouse A",
    "initialStatus": "In Stock",
    "unitCount": 150,
    "lowStockThreshold": 20
  }'
```

#### Access Protected User Route

```bash
curl -X GET http://localhost:5000/v1/user \
  -b cookies.txt
```

### Using JavaScript/Fetch

#### Register

```javascript
fetch('http://localhost:5000/v1/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    first_name: 'John',
    last_name: 'Doe',
    email: 'john@example.com',
    password: 'SecurePassword123'
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

#### Login

```javascript
fetch('http://localhost:5000/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  credentials: 'include',
  body: JSON.stringify({
    email: 'john@example.com',
    password: 'SecurePassword123'
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

#### Create Employee

```javascript
fetch('http://localhost:5000/v1/employees', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    fullName: 'Alice Johnson',
    department: 'Engineering',
    jobTitle: 'Senior Developer',
    location: 'San Francisco, CA',
    workEmail: 'alice.johnson@company.com'
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

---

## Best Practices

### Security

1. **Always use HTTPS in production** - All requests should be made over secure connections
2. **Validate input** - The API validates all inputs server-side; additionally validate on the client
3. **Store JWT securely** - The JWT is stored in an HTTP-only cookie and is inaccessible to JavaScript
4. **Keep passwords strong** - Passwords are hashed with bcrypt and should be at least 8 characters
5. **Use unique emails** - Email addresses must be unique per user and employee
6. **Token expiration** - Sessions expire after 20 minutes; users must re-authenticate
7. **Logout to invalidate** - Always call logout endpoint to properly blacklist tokens

### API Usage

1. **Check status field** - Responses include a `status` field ("success", "failed", "error") to indicate outcome
2. **Handle HTTP status codes** - Different status codes indicate different outcomes (200, 201, 400, 401, 404, 500)
3. **Use valid MongoDB IDs** - Path parameters for ID require valid MongoDB ObjectIds
4. **Trim whitespace** - String inputs are automatically trimmed; provide clean data
5. **Validate enum values** - Lead priority/stage and product status must be from predefined enums
6. **Unique constraints** - SKU, email, and work email fields have unique constraints
7. **Date format** - Invoice dates should be ISO8601 format (e.g., "2024-05-03T00:00:00Z")
8. **Currency codes** - Use standard uppercase currency codes (USD, EUR, GBP, etc.)

### Performance

1. **Batch requests** - Group multiple operations when possible
2. **Pagination ready** - While not currently implemented, plan for pagination on large datasets
3. **Use GET for retrieval** - Use GET endpoints for read-only operations
4. **Use POST for creation** - Use POST when creating new resources
5. **Use PUT for updates** - Use PUT for partial or full updates
6. **Use DELETE for removal** - Use DELETE to remove resources

### Error Handling

1. **Check response status** - Always check the HTTP status code and `status` field
2. **Handle validation errors** - 400 errors include validation messages
3. **Re-authenticate on 401** - Redirect to login if session expires
4. **Implement retry logic** - For transient errors (5xx), implement exponential backoff
5. **Log errors** - Log errors for debugging and monitoring
6. **Provide user feedback** - Display meaningful error messages to end users

### Data Validation

| Field | Type | Min/Max | Format | Constraints |
|-------|------|---------|--------|-------------|
| first_name | String | - | - | Max 25 chars, required |
| last_name | String | - | - | Max 25 chars, required |
| email | String | - | Email | Valid format, unique, lowercase |
| password | String | 8 chars | - | Min 8 chars, hashed with bcrypt |
| fullName | String | - | - | Required, trimmed |
| workEmail | String | - | Email | Valid format, unique |
| dealValue | Number | 0 | - | Must be >= 0 |
| priority | Enum | - | Low, Medium, High | One of three values |
| stage | Enum | - | New, Contacted, Qualified, Proposal, Closed Won, Closed Lost | One of six values |
| issueDate | Date | - | ISO8601 | Valid date |
| dueDate | Date | - | ISO8601 | Valid date, typically after issueDate |
| quantity | Number | 1 | - | Integer >= 1 |
| unitPrice | Number | 0 | - | Float >= 0 |
| customTaxRate | Number | 0-100 | - | Percentage between 0-100 |
| sku | String | - | - | Unique, uppercase |
| unitCount | Number | 0 | - | Integer >= 0 |
| lowStockThreshold | Number | 0 | - | Integer >= 0 |

### Rate Limiting

Currently, the API does not have rate limiting implemented. Clients should implement:
- Reasonable delays between requests
- Connection pooling for multiple concurrent requests
- Exponential backoff for retries

---

## Support & Troubleshooting

### Common Issues

**Invalid email format**
- Ensure email follows standard format: `user@domain.com`
- Email is automatically normalized to lowercase

**MongoDB ObjectId validation**
- ID must be a valid 24-character hexadecimal string
- Example: `507f1f77bcf86cd799439011`

**Session expired**
- Session tokens expire after 20 minutes
- Call the `/v1/auth/login` endpoint again to get a new token

**Duplicate resource**
- Attempt to create duplicate email or SKU
- Check existing records or use unique identifiers

**Validation errors on nested objects**
- Invoice line items require all nested properties
- Use dot notation for nested validations (e.g., `clientInformation.customerName`)

---

## Version History

- **v1** (Current) - Initial API release with employee, lead, invoice, and product management

---

**Last Updated:** May 3, 2024  
**API Version:** 1.0.0  
**Status:** Production Ready
