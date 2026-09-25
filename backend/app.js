require("dotenv").config();

const express = require("express");
const cors = require("cors");
const multer = require("multer");
const helmet = require("helmet");
const rateLimit = require("express-rate-limit");

const headerMappingRoutes = require("./routes/headerMappingRoutes");
const authRoutes = require("./routes/authRoutes");
const uploadRoutes = require("./routes/uploadroutes");
const adminRoutes = require("./routes/adminRoutes");
const validationRoutes = require("./routes/validationRoutes");
const transformationRoutes = require("./routes/transformationRoutes");
const analyticsRoutes = require("./routes/analyticsRoutes");
const datasetLibraryRoutes = require("./routes/datasetLibraryRoutes");
const authMiddleware = require("./middleware/authMiddleware");
const adminMiddleware = require("./middleware/adminMiddleware");

const app = express();
const PORT = process.env.PORT || 5000;

app.use(helmet());
app.use(cors());
app.use(express.json({ limit: "1mb" }));

const authLimiter = rateLimit({ windowMs: 15 * 60 * 1000, limit: 50, standardHeaders: "draft-8", legacyHeaders: false });
const uploadLimiter = rateLimit({ windowMs: 15 * 60 * 1000, limit: 60, standardHeaders: "draft-8", legacyHeaders: false });
app.use("/api/auth/login", authLimiter);
app.use("/api/auth/register", authLimiter);

app.get("/api/health", (req, res) => {
    res.json({ success: true, message: "Project Alpha backend is running" });
});
app.use("/api/auth", authRoutes);
app.use("/api/upload", authMiddleware, uploadLimiter, uploadRoutes);
app.use("/api/admin", authMiddleware, adminMiddleware, adminRoutes);
app.use("/api/header-mapping",authMiddleware,headerMappingRoutes);
app.use("/api/validation", authMiddleware, validationRoutes);
app.use("/api/transformation", authMiddleware, transformationRoutes);
app.use("/api/analytics", authMiddleware, analyticsRoutes);
app.use("/api/datasets", authMiddleware, datasetLibraryRoutes);

app.use((err, req, res, next) => {
    const isUploadRequest = req.originalUrl.startsWith("/api/upload");
    const status = err instanceof multer.MulterError ? 400 : err.status || (isUploadRequest ? 400 : 500);
    if (status >= 500) console.error(err);
    return res.status(status).json({
        success: false,
        code: err.code || undefined,
        message: status >= 500 ? "Internal server error" : err.message,
        details: status < 500 ? err.details : undefined
    });
});

if (require.main === module) {
    app.listen(PORT, () => {
        console.log(`Project Alpha backend is running on port ${PORT}`);
    });
}

module.exports = app;
