// controllers/lead.controller.js

import Lead from "../models/Lead.js";
import Inventory from "../models/inventoryModel.js";
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

export const addProductToLead = async (req, res, next) => {
  try {
    const lead = await Lead.findById(req.params.id);

    if (!lead) {
      throw new AppError("Lead not found", 404);
    }

    const productPayload = {
      productName: req.body.productName?.trim(),
      category: req.body.category?.trim(),
      price: Number(req.body.price),
      sku: req.body.sku?.trim().toUpperCase(),
    };

    if (!productPayload.productName) {
      throw new AppError("productName is required", 400);
    }

    if (!productPayload.category) {
      throw new AppError("category is required", 400);
    }

    if (!Number.isFinite(productPayload.price) || productPayload.price <= 0) {
      throw new AppError("price must be greater than 0", 400);
    }

    if (!productPayload.sku) {
      throw new AppError("sku is required", 400);
    }

    lead.products = lead.products || [];
    lead.products.push({
      ...productPayload,
      createdAt: new Date(),
    });

    await lead.save();

    return res.status(200).json({
      status: "success",
      data: lead,
      message: "Product added to lead successfully",
    });
  } catch (error) {
    return next(error);
  }
};

export const updateProductInLead = async (req, res, next) => {
  try {
    const lead = await Lead.findById(req.params.leadId);

    if (!lead) {
      throw new AppError("Lead not found", 404);
    }

    const product = lead.products?.id(req.params.productId);

    if (!product) {
      throw new AppError("Product not found", 404);
    }

    const productPayload = {
      productName: req.body.productName?.trim(),
      category: req.body.category?.trim(),
      price: Number(req.body.price),
      sku: req.body.sku?.trim().toUpperCase(),
    };

    if (!productPayload.productName) {
      throw new AppError("productName is required", 400);
    }

    if (!productPayload.category) {
      throw new AppError("category is required", 400);
    }

    if (!Number.isFinite(productPayload.price) || productPayload.price <= 0) {
      throw new AppError("price must be greater than 0", 400);
    }

    if (!productPayload.sku) {
      throw new AppError("sku is required", 400);
    }

    product.set(productPayload);
    await lead.save();

    return res.status(200).json({
      status: "success",
      data: lead,
      message: "Product updated successfully",
    });
  } catch (error) {
    return next(error);
  }
};

export const deleteProductFromLead = async (req, res, next) => {
  try {
    const lead = await Lead.findById(req.params.leadId);

    if (!lead) {
      throw new AppError("Lead not found", 404);
    }

    const hasProduct = lead.products?.some((item) => String(item._id) === String(req.params.productId));

    if (!hasProduct) {
      throw new AppError("Product not found", 404);
    }

    lead.products = (lead.products || []).filter((item) => String(item._id) !== String(req.params.productId));
    await lead.save();

    return res.status(200).json({
      status: "success",
      data: lead,
      message: "Product removed successfully",
    });
  } catch (error) {
    return next(error);
  }
};

export const getInventorySuggestions = async (req, res, next) => {
  try {
    const query = req.query.q?.trim() || "";

    if (!query) {
      return res.status(200).json({
        status: "success",
        data: [],
        message: "No suggestions",
      });
    }

    const searchRegex = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "i");
    const suggestions = await Inventory.find({
      $or: [{ name: searchRegex }, { sku: searchRegex }],
    })
      .select("name category price sku")
      .sort({ createdAt: -1 })
      .limit(10)
      .lean();

    const formattedSuggestions = suggestions.map((item) => ({
      _id: item._id,
      productName: item.name,
      category: item.category,
      price: item.price,
      sku: item.sku,
    }));

    return res.status(200).json({
      status: "success",
      data: formattedSuggestions,
      message: "Product suggestions fetched successfully",
    });
  } catch (error) {
    return next(error);
  }
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
