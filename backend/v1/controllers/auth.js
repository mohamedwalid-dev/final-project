import User from "../models/User.js";
import Blacklist from '../models/Black-List.js';
import bcrypt from "bcrypt";
import { sendSuccess } from "../utils/response.js";
import AppError from "../utils/AppError.js";

function getCookieOptions() {
  const isProd = process.env.NODE_ENV === "production";
  return {
    maxAge: 20 * 60 * 1000, // 20 minutes
    httpOnly: true,
    secure: isProd, // localhost dev must be false
    sameSite: isProd ? "none" : "lax",
  };
}
/**
 * @route POST v1/auth/register
 * @desc Registers a user
 * @access Public
 */

/**
 * @route POST v1/auth/login
 * @desc logs in a user
 * @access Public
 */

export async function Register(req, res, next) {
    // get required variables from request body
    // using es6 object destructing
    const { first_name, last_name, email, password } = req.body;
    const hashedPassword = await bcrypt.hash(password, 10);
    try {
        // Check if user already exists
        const existingUser = await User.findOne({ email });
        if (existingUser)
            throw new AppError("It seems you already have an account, please log in instead.", 400);

        // create an instance of a user
        const newUser = new User({
            first_name,
            last_name,
            email,
            password: hashedPassword
        });
        const savedUser = await newUser.save(); // save new user into the database
        const { role, ...user_data } = savedUser._doc;

        const token = savedUser.generateAccessJWT();
        res.cookie("SessionID", token, getCookieOptions());

        return sendSuccess(
          res,
          user_data,
          "Thank you for registering with us. Your account has been successfully created.",
          201
        );
    } catch (err) {
        return next(err);
    }
}

export async function Login(req, res, next) {
    // Get variables for the login process
    const { email } = req.body;
    try {
        // Check if user exists
        const user = await User.findOne({ email }).select("+password");
        if (!user)
            throw new AppError("Account does not exist", 401);
        // if user exists
        // validate password
        const isPasswordValid = await bcrypt.compare(
            `${req.body.password}`,
            user.password
        );
        // if not valid, return unathorized response
        if (!isPasswordValid)
            throw new AppError("Invalid email or password. Please try again with the correct credentials.", 401);

        const token = user.generateAccessJWT(); // generate session token for user
        res.cookie("SessionID", token, getCookieOptions()); // cookie-based auth

        const { password, ...user_data } = user._doc;
        return res.json({
            success: true,
            message: "You are now logged in!",
            token
        })
    } catch (err) {
        return next(err);
    }
}

export async function Logout(req, res, next) {
  try {
    const accessToken = req.cookies?.SessionID;
    if (!accessToken) return res.sendStatus(204); // No content
    const checkIfBlacklisted = await Blacklist.findOne({ token: accessToken }); // Check if that token is blacklisted
    // if true, send a no content response.
    if (checkIfBlacklisted) return res.sendStatus(204);
    // otherwise blacklist token
    const newBlacklist = new Blacklist({
      token: accessToken,
    });
    await newBlacklist.save();
    res.clearCookie("SessionID", getCookieOptions());
    return sendSuccess(res, [], "You are logged out!", 200);
  } catch (err) {
    return next(err);
  }
}

export async function Me(req, res) {
  // req.user is set by Verify middleware
  return sendSuccess(res, req.user ?? [], "Authenticated user", 200);
}
