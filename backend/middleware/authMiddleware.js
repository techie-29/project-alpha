const jwt = require("jsonwebtoken");
const db = require("../config/db");

async function authMiddleware(req, res, next) {
    const authHeader = req.headers.authorization || "";
    const [scheme, token] = authHeader.split(" ");

    if (scheme !== "Bearer" || !token) {
        return res.status(401).json({
            success: false,
            message: "Authentication token required"
        });
    }

    try {
        const decoded = jwt.verify(token, process.env.JWT_SECRET);
        const [accounts] = await db.execute(
            `SELECT id, email, role, account_status AS accountStatus
             FROM business_accounts
             WHERE id = ?`,
            [decoded.id]
        );

        if (accounts.length === 0) {
            return res.status(401).json({
                success: false,
                message: "Account no longer exists"
            });
        }

        const account = accounts[0];
        if (account.accountStatus === "disabled") {
            return res.status(403).json({
                success: false,
                message: "This business account has been disabled by an administrator"
            });
        }

        req.user = {
            id: account.id,
            email: account.email,
            role: account.role
        };
        next();
    } catch (error) {
        if (error.name === "JsonWebTokenError" || error.name === "TokenExpiredError") {
            return res.status(401).json({
                success: false,
                message: "Invalid or expired token"
            });
        }
        next(error);
    }
}

module.exports = authMiddleware;
