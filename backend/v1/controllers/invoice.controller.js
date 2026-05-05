// controllers/invoice.controller.js

import Invoice from "../models/Invoice.js";
import AppError from "../utils/AppError.js";
import { sendSuccess } from "../utils/response.js";

export const createInvoice = async (req, res) => {
  try {
    const payload = {
      ...req.body,
      status: req.body.status || "Pending",
    };

    const invoice = await Invoice.create(payload);

    return res.status(201).json({
      status: "success",
      data: invoice,
      message: "Invoice created successfully",
    });
  } catch (error) {
    return res.status(500).json({
      status: "failed",
      data: [],
      message: error.message,
    });
  }
};

export const getAllInvoices = async (req, res, next) => {
  try {
    const invoices = await Invoice.find();

    return sendSuccess(res, invoices, "Invoices fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const getInvoiceById = async (req, res, next) => {
  try {
    const invoice = await Invoice.findById(req.params.id);

    if (!invoice) {
      throw new AppError("Invoice not found", 404);
    }

    return sendSuccess(res, invoice, "Invoice fetched successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const updateInvoice = async (req, res, next) => {
  try {
    const invoice = await Invoice.findByIdAndUpdate(
      req.params.id,
      req.body,
      { new: true, runValidators: true }
    );

    if (!invoice) {
      throw new AppError("Invoice not found", 404);
    }

    return sendSuccess(res, invoice, "Invoice updated successfully", 200);
  } catch (error) {
    return next(error);
  }
};

export const deleteInvoice = async (req, res, next) => {
  try {
    const invoice = await Invoice.findByIdAndDelete(req.params.id);

    if (!invoice) {
      throw new AppError("Invoice not found", 404);
    }

    return sendSuccess(res, [], "Invoice deleted successfully", 200);
  } catch (error) {
    return next(error);
  }
};
