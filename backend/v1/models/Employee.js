
import mongoose from 'mongoose';

const leaveRequestSchema = new mongoose.Schema({
  fullName: {
    type: String,
    required: true,
    trim: true,
  },
  employeeId: {
    type: String,
    required: true,
    trim: true,
  },
  leaveType: {
    type: String,
    required: true,
    trim: true,
  },
  leaveBalance: {
    type: Number,
    required: true,
    min: 0,
  },
  leaveStartDate: {
    type: Date,
    required: true,
  },
  leaveEndDate: {
    type: Date,
    required: true,
  },
  reason: {
    type: String,
    required: true,
    trim: true,
  },
  status: {
    type: String,
    enum: ["Pending", "Approved", "Rejected"],
    default: "Pending",
  },
}, {
  timestamps: true,
});

const employeeSchema = new mongoose.Schema({
  fullName: {
    type: String,
    required: true,
    trim: true,
  },
  employeeId: {
    type: String,
    required: true,
    unique: true,
    trim: true,
    index: true,
  },
  department: {
    type: String,
    required: true,
    trim: true,
  },
  jobTitle: {
    type: String,
    required: true,
    trim: true,
  },
  location: {
    type: String,
    required: true,
    trim: true,
  },
  workEmail: {
    type: String,
    required: true,
    unique: true,
    lowercase: true,
    trim: true,
    match: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  },
  salary: {
    type: Number,
    min: 0,
  },
  phoneNumber: {
    type: String,
    trim: true,
  },
  startDate: {
    type: Date,
  },
  dateOfBirth: {
    type: Date,
  },
  gender: {
    type: String,
    enum: ["Male", "Female", "Prefer not to say"],
    trim: true,
  },
  leaveRequests: [leaveRequestSchema],
}, {
  timestamps: true,
});

export default mongoose.model("Employee", employeeSchema);