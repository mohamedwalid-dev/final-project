// controllers/lead.controller.js

import Lead from "../models/Lead.js";
import AppError from "../utils/AppError.js";
import { sendSuccess } from "../utils/response.js";

export const createLead = async (req, res, next) => {
  try {
    const lead = await Lead.create(req.body);

    return sendSuccess(res, lead, "Lead created successfully", 201);
  } catch (error) {
    return next(error);
  }
};

export const getAllLeads = async (req, res, next) => {
  try {
    const leads = await Lead.find().sort({ createdAt: -1 });

    return sendSuccess(res, leads, "Leads fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const getLeadById = async (req, res, next) => {
  try {
    const lead = await Lead.findById(req.params.id);

    if (!lead) {
      throw new AppError("Lead not found", 404);
    }

    return sendSuccess(res, lead, "Lead fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const updateLead = async (req, res, next) => {
  try {
    const lead = await Lead.findByIdAndUpdate(
      req.params.id,
      req.body,
      { new: true, runValidators: true }
    );

    if (!lead) {
      throw new AppError("Lead not found", 404);
    }

    return sendSuccess(res, lead, "Lead updated successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const deleteLead = async (req, res, next) => {
  try {
    const lead = await Lead.findByIdAndDelete(req.params.id);

    if (!lead) {
      throw new AppError("Lead not found", 404);
    }

    return sendSuccess(res, [], "Lead deleted successfully", 200);
  } catch (error) {
    return next(error);
  }
};
