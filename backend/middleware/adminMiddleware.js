const db = require("../config/db");

async function adminMiddleware(req, res, next) {
    if (!req.user?.id) {
        return res.status(403).json({ success: false, message: "Admin access required" });
    }

    try {
        // Do not trust an old JWT role for administrative authority.
        // Read the current role/status so a DB change takes effect immediately.
        const [accounts] = await db.execute(
            `SELECT role, account_status AS accountStatus
             FROM business_accounts
             WHERE id = ?`,
            [req.user.id]
        );

        const account = accounts[0];
        if (!account || account.role !== "admin" || account.accountStatus !== "active") {
            return res.status(403).json({ success: false, message: "Active administrator access required" });
        }

        req.user.role = account.role;
        next();
    } catch (error) {
        next(error);
    }
}

module.exports = adminMiddleware;
