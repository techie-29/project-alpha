const express = require("express");
const bcrypt = require("bcrypt");
const jwt = require("jsonwebtoken");

const db = require("../config/db");
const authMiddleware = require("../middleware/authMiddleware");

const router = express.Router();

function createToken(account) {
    return jwt.sign(
        { id: account.id, email: account.email },
        process.env.JWT_SECRET,
        { expiresIn: "1h" }
    );
}

function publicAccount(account) {
    return {
        id: account.id,
        businessName: account.business_name,
        email: account.email
    };
}

router.post("/register", async (req, res, next) => {
    try {
        const businessName = req.body.businessName?.trim();
        const email = req.body.email?.trim().toLowerCase();
        const password = req.body.password;

        if (!businessName || !email || !password) {
            return res.status(400).json({
                success: false,
                message: "Business name, email, and password are required"
            });
        }

        if (password.length < 6) {
            return res.status(400).json({
                success: false,
                message: "Password must contain at least 6 characters"
            });
        }

        const [existingAccounts] = await db.execute(
            "SELECT id FROM business_accounts WHERE email = ?",
            [email]
        );

        if (existingAccounts.length > 0) {
            return res.status(409).json({
                success: false,
                message: "An account with this email already exists"
            });
        }

        const passwordHash = await bcrypt.hash(password, 10);
        const [result] = await db.execute(
            `INSERT INTO business_accounts
                (business_name, email, password_hash)
             VALUES (?, ?, ?)`,
            [businessName, email, passwordHash]
        );

        const account = {
            id: result.insertId,
            business_name: businessName,
            email
        };

        return res.status(201).json({
            success: true,
            message: "Business account created successfully",
            data: {
                token: createToken(account),
                account: publicAccount(account)
            }
        });
    } catch (error) {
        if (error.code === "ER_DUP_ENTRY") {
            return res.status(409).json({
                success: false,
                message: "An account with this email already exists"
            });
        }

        next(error);
    }
});

router.post("/login", async (req, res, next) => {
    try {
        const email = req.body.email?.trim().toLowerCase();
        const password = req.body.password;

        if (!email || !password) {
            return res.status(400).json({
                success: false,
                message: "Email and password are required"
            });
        }

        const [accounts] = await db.execute(
            `SELECT id, business_name, email, password_hash
             FROM business_accounts
             WHERE email = ?`,
            [email]
        );

        if (accounts.length === 0) {
            return res.status(401).json({
                success: false,
                message: "Invalid email or password"
            });
        }

        const account = accounts[0];
        const passwordMatches = await bcrypt.compare(
            password,
            account.password_hash
        );

        if (!passwordMatches) {
            return res.status(401).json({
                success: false,
                message: "Invalid email or password"
            });
        }

        return res.json({
            success: true,
            message: "Login successful",
            data: {
                token: createToken(account),
                account: publicAccount(account)
            }
        });
    } catch (error) {
        next(error);
    }
});

router.get("/me", authMiddleware, async (req, res, next) => {
    try {
        const [accounts] = await db.execute(
            `SELECT id, business_name, email
             FROM business_accounts
             WHERE id = ?`,
            [req.user.id]
        );

        if (accounts.length === 0) {
            return res.status(404).json({
                success: false,
                message: "Account not found"
            });
        }

        return res.json({
            success: true,
            data: { account: publicAccount(accounts[0]) }
        });
    } catch (error) {
        next(error);
    }
});

module.exports = router;
