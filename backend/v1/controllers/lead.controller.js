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

  if (typeof payload.assignedTo === "string") {
    nextPayload.assignedTo = payload.assignedTo.trim() || "Unassigned";
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

const buildLeadAnalytics = async (LeadModel) => {
  const [analyticsResult] = await LeadModel.aggregate([
    {
      $facet: {
        summary: [
          {
            $group: {
              _id: null,
              totalLeads: { $sum: 1 },
              totalRevenue: { $sum: "$dealValue" },
              wonDeals: {
                $sum: { $cond: [{ $eq: ["$status", "Won"] }, 1, 0] },
              },
              lostDeals: {
                $sum: { $cond: [{ $eq: ["$status", "Lost"] }, 1, 0] },
              },
              activeOpportunities: {
                $sum: { $cond: [{ $eq: ["$status", "Open"] }, 1, 0] },
              },
              qualifiedLeads: {
                $sum: {
                  $cond: [{ $in: ["$stage", ["Contacted", "Proposal", "Negotiation", "Closed", "Closed Won", "Closed Lost"]] }, 1, 0],
                },
              },
            },
          },
          {
            $project: {
              _id: 0,
              totalLeads: 1,
              totalRevenue: 1,
              wonDeals: 1,
              lostDeals: 1,
              activeOpportunities: 1,
              qualifiedLeads: 1,
            },
          },
        ],
        monthlyRevenue: [
          { $match: { status: "Won", dealValue: { $gt: 0 } } },
          {
            $group: {
              _id: {
                month: { $dateToString: { format: "%Y-%m", date: "$updatedAt" } },
              },
              revenue: { $sum: "$dealValue" },
            },
          },
          { $project: { _id: 0, month: "$_id.month", revenue: 1 } },
          { $sort: { month: 1 } },
        ],
        winLoss: [
          {
            $group: {
              _id: "$status",
              count: { $sum: 1 },
            },
          },
          {
            $project: {
              _id: 0,
              name: {
                $cond: [{ $eq: ["$_id", "Won"] }, "Won", { $cond: [{ $eq: ["$_id", "Lost"] }, "Lost", "Open"] }],
              },
              count: 1,
            },
          },
          { $sort: { name: 1 } },
        ],
        pipelineByStage: [
          {
            $group: {
              _id: "$stage",
              count: { $sum: 1 },
              value: { $sum: "$dealValue" },
            },
          },
          { $project: { _id: 0, stage: "$_id", count: 1, value: 1 } },
          { $sort: { value: -1 } },
        ],
        topReps: [
          {
            $group: {
              _id: { $ifNull: ["$assignedTo", "Unassigned"] },
              deals: { $sum: 1 },
              revenue: { $sum: "$dealValue" },
            },
          },
          { $project: { _id: 0, name: "$_id", deals: 1, revenue: 1 } },
          { $sort: { revenue: -1 } },
          { $limit: 5 },
        ],
      },
    },
  ]);

  const summary = analyticsResult?.summary?.[0] || {};
  const totalLeads = Number(summary.totalLeads || 0);
  const totalRevenue = Number(summary.totalRevenue || 0);
  const wonDeals = Number(summary.wonDeals || 0);
  const lostDeals = Number(summary.lostDeals || 0);
  const activeOpportunities = Number(summary.activeOpportunities || 0);
  const qualifiedLeads = Number(summary.qualifiedLeads || 0);
  const conversionRate = totalLeads > 0 ? (wonDeals / totalLeads) * 100 : 0;
  const averageDealSize = totalLeads > 0 ? totalRevenue / totalLeads : 0;

  const monthlyRevenue = (analyticsResult?.monthlyRevenue || []).map((entry) => ({
    month: entry.month,
    revenue: Number(entry.revenue || 0),
  }));

  const winLossData = (analyticsResult?.winLoss || [])
    .filter((entry) => entry.name === "Won" || entry.name === "Lost")
    .map((entry) => ({
      name: entry.name,
      value: Number(entry.count || 0),
    }));

  const totalClosedDeals = wonDeals + lostDeals;
  const winLoss = [
    {
      name: "Won",
      value: totalClosedDeals > 0 ? Number(((wonDeals / totalClosedDeals) * 100).toFixed(1)) : 0,
    },
    {
      name: "Lost",
      value: totalClosedDeals > 0 ? Number(((lostDeals / totalClosedDeals) * 100).toFixed(1)) : 0,
    },
  ];

  return {
    summary: {
      totalLeads,
      totalRevenue,
      wonDeals,
      lostDeals,
      activeOpportunities,
      qualifiedLeads,
      conversionRate: Number(conversionRate.toFixed(1)),
      averageDealSize: Number(averageDealSize.toFixed(0)),
    },
    monthlyRevenue,
    winLoss,
    pipelineByStage: (analyticsResult?.pipelineByStage || []).map((entry) => ({
      stage: entry.stage,
      count: Number(entry.count || 0),
      value: Number(entry.value || 0),
    })),
    topReps: (analyticsResult?.topReps || []).map((entry) => ({
      name: entry.name,
      deals: Number(entry.deals || 0),
      revenue: Number(entry.revenue || 0),
    })),
    winLossData,
  };
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
    const [leads, analytics] = await Promise.all([
      Lead.find().sort({ createdAt: -1 }).lean(),
      buildLeadAnalytics(Lead),
    ]);

    return res.status(200).json({
      status: "success",
      data: leads,
      analytics,
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
