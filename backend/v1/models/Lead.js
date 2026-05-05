import mongoose from 'mongoose';

const LeadSchema = new mongoose.Schema({
  companyName: {
    type: String,
    required: true,
    trim: true
  },

  dealValue: {
    type: Number,
    required: true,
    min: 0
  },

  priority: {
    type: String,
    required: true,
    enum: ["Low", "Medium", "High"]
  },

  stage: {
    type: String,
    required: true,
    enum: ["New", "Contacted", "Qualified", "Proposal", "Closed Won", "Closed Lost"]
  }

}, {
  timestamps: true // adds createdAt & updatedAt
});

export default mongoose.model("Lead", LeadSchema);