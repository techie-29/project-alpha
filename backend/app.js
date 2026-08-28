require("dotenv").config();

const express = require("express");
const cors = require("cors");
const multer = require("multer");

const authRoutes = require("./routes/authRoutes");
const uploadRoutes = require("./routes/uploadroutes");
const authMiddleware = require("./middleware/authMiddleware");

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

app.get("/api/health", (req, res) => {
    res.json({ success: true, message: "Project Alpha backend is running" });
});

app.use("/api/auth", authRoutes);
app.use("/api/upload", authMiddleware, uploadRoutes);

app.use((err, req, res, next) => {
    const isUploadRequest = req.originalUrl.startsWith("/api/upload");
    const status = err instanceof multer.MulterError
        ? 400
        : err.status || (isUploadRequest ? 400 : 500);

    if (status >= 500) {
        console.error(err);
    }

    return res.status(status).json({
        success: false,
        message: status >= 500 ? "Internal server error" : err.message
    });
});

app.listen(PORT, () => {
    console.log(`Project Alpha backend is running on port ${PORT}`);
});
