// controllers/lead.controller.js

import Lead from "../models/Lead.js";
import AppError from "../utils/AppError.js";

const normalizePriority = (value) => {
  if (typeof value !== "string") return "Medium";

  const normalized = value.trim();
  if (["Low", "Medium", "High"].includes(normalized)) {
    return normalized;
  }

  return normalized.charAt(0).toUpperCase() + normalized.slice(1).toLowerCase();
};

const normalizeStage = (value, status) => {
  if (typeof value !== "string") return "New";

  const normalized = value.trim();
  if (status === "Won" || normalized === "Closed Won" || normalized === "Closed") return "Closed Won";
  if (status === "Lost" || normalized === "Closed Lost") return "Closed Lost";

  const allowedStages = ["New", "Contacted", "Proposal", "Negotiation", "Closed", "Closed Won", "Closed Lost"];
  return allowedStages.includes(normalized) ? normalized : "New";
};

const normalizeStatus = (value, stage) => {
  if (typeof value !== "string") return "Open";

  const normalized = value.trim();
  if (["Won", "Lost"].includes(normalized)) return normalized;
  if (stage === "Closed Won") return "Won";
  if (stage === "Closed Lost") return "Lost";
  return "Open";
};

const buildLeadPayload = (payload = {}, { forCreate = false } = {}) => {
  const nextPayload = { ...payload };

  if (typeof payload.clientName === "string" && payload.clientName.trim()) {
    nextPayload.clientName = payload.clientName.trim();
  }

  if (typeof payload.companyName === "string" && payload.companyName.trim()) {
    nextPayload.companyName = payload.companyName.trim();
  } else if (nextPayload.clientName) {
    nextPayload.companyName = nextPayload.clientName;
  }

  if (typeof payload.email === "string") {
    nextPayload.email = payload.email.trim().toLowerCase();
  }

  if (typeof payload.address === "string") {
    nextPayload.address = payload.address.trim();
  }

  if (typeof payload.phone === "string") {
    nextPayload.phone = payload.phone.trim();
  }

  if (payload.dealValue !== undefined) {
    const parsedValue = Number(payload.dealValue);
    nextPayload.dealValue = Number.isFinite(parsedValue) ? parsedValue : 0;
  }

  if (payload.priority !== undefined) {
    nextPayload.priority = normalizePriority(payload.priority);
  }

  if (payload.stage !== undefined) {
    nextPayload.stage = normalizeStage(payload.stage, payload.status);
  }

  if (payload.status !== undefined) {
    nextPayload.status = normalizeStatus(payload.status, nextPayload.stage);
  }

  if (forCreate) {
    if (!nextPayload.clientName && !nextPayload.companyName) {
      nextPayload.clientName = "Untitled lead";
      nextPayload.companyName = "Untitled lead";
    }

    if (!nextPayload.email) {
      nextPayload.email = "lead@example.com";
    }

    nextPayload.priority ??= "Medium";
    nextPayload.stage ??= "New";
    nextPayload.status ??= "Open";
    nextPayload.dealValue ??= 0;
  }

  return nextPayload;
};

export const createLead = async (req, res, next) => {
  try {
    const lead = await Lead.create(buildLeadPayload(req.body, { forCreate: true }));

    return res.status(201).json({
      status: "success",
      data: lead,
      message: "Lead created successfully",
    });
  } catch (error) {
    return next(error);
  }
};

export const getAllLeads = async (req, res, next) => {
  try {
    const leads = await Lead.find().sort({ createdAt: -1 });

    return res.status(200).json({
      status: "success",
      data: leads,
      message: "Leads fetched successfully",
    });
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

    return res.status(200).json({
      status: "success",
      data: lead,
      message: "Lead fetched successfully",
    });
  } catch (error) {
    return next(error);
  }
};

export const updateLead = async (req, res, next) => {
  try {
    const lead = await Lead.findByIdAndUpdate(
      req.params.id,
      buildLeadPayload(req.body),
      { new: true, runValidators: true }
    );

    if (!lead) {
      throw new AppError("Lead not found", 404);
    }

    return res.status(200).json({
      status: "success",
      data: lead,
      message: "Lead updated successfully",
    });
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

    return res.status(200).json({
      status: "success",
      data: [],
      message: "Lead deleted successfully",
    });
  } catch (error) {
    return next(error);
  }
};
