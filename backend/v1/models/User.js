import mongoose from "mongoose";
import jwt from "jsonwebtoken";
import { SECRET_ACCESS_TOKEN } from "../config/index.js";

export const VALID_USER_ROLES = [
  "client",
  "support",
  "accountant",
  "hr",
  "sales",
  "manager",
  "admin",
];

export const VALID_USER_DEPARTMENTS = [
  "client",
  "support",
  "finance",
  "accounting",
  "hr",
  "sales",
  "management",
  "admin",
];

const UserSchema = new mongoose.Schema(
  {
    name: {
      type: String,
      trim: true,
      maxLength: 80,
    },
    first_name: {
      type: String,
      trim: true,
      maxLength: 25,
    },
    last_name: {
      type: String,
      trim: true,
      maxLength: 25,
    },
    email: {
      type: String,
      required: "Your email is required",
      unique: true,
      lowercase: true,
      trim: true,
    },
    password: {
      type: String,
      required: "Your password is required",
      select: false,
    },
    role: {
      type: String,
      enum: VALID_USER_ROLES,
      default: "client",
      required: true,
    },
    department: {
      type: String,
      enum: VALID_USER_DEPARTMENTS,
      default: "client",
      required: true,
    },
    isActive: {
      type: Boolean,
      default: true,
    },
  },
  { timestamps: true }
);

UserSchema.pre("validate", function normalizeName(next) {
  if (!this.name && (this.first_name || this.last_name)) {
    this.name = [this.first_name, this.last_name].filter(Boolean).join(" ").trim();
  }

  if (this.name && (!this.first_name || !this.last_name)) {
    const [firstName = "", ...rest] = this.name.trim().split(/\s+/);
    if (!this.first_name) this.first_name = firstName;
    if (!this.last_name) this.last_name = rest.join(" ") || firstName;
  }

  next();
});

UserSchema.methods.generateAccessJWT = function generateAccessJWT() {
  return jwt.sign(
    {
      id: this._id,
      role: this.role,
      department: this.department,
    },
    SECRET_ACCESS_TOKEN,
    {
      expiresIn: "20m",
    }
  );
};

UserSchema.methods.toJSON = function toJSON() {
  const user = this.toObject();
  delete user.password;
  return user;
};

export default mongoose.model("users", UserSchema);
