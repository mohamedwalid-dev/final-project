
import mongoose from 'mongoose';

const employeeSchema = new mongoose.Schema({
  fullName: {
    type: String,
    required: true,
    trim: true,
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
}, {
  timestamps: true,
});

export default mongoose.model("Employee", employeeSchema);