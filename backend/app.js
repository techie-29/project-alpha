// const express = require("express");
// const multer = require("multer");
// const path = require("path");

// const app = express();
// const port = 5000;

// const allowedExtensions = [".csv", ".xlsx", ".xls"];

// const upload = multer({
//     dest: "uploads/",

//     limits: {
//         fileSize: 10 * 1024 * 1024
//     },

//     fileFilter: (req, file, cb) => {
//         const extension = path.extname(file.originalname).toLowerCase();

//         if (allowedExtensions.includes(extension)) {
//             cb(null, true);
//         } else {
//             cb(new Error("Only CSV and Excel files are allowed"));
//         }
//     }
// });

// app.post("/api/upload", upload.single("file"), (req, res) => {
//     if (!req.file) {
//         return res.status(400).json({
//             success: false,
//             message: "No file uploaded"
//         });
//     }

//     return res.json({
//         success: true,
//         message: "File received successfully",
//         file: req.file
//     });
// });

// app.use((err, req, res, next) => {
//     if (err instanceof multer.MulterError) {
//         return res.status(400).json({
//             success: false,
//             message: err.message
//         });
//     }

//     if (err) {
//         return res.status(400).json({
//             success: false,
//             message: err.message
//         });
//     }

//     next();
// });

// app.listen(port, () => {
//     console.log(`Backend is running on port: ${port}`);
// });

const express = require("express");
const cors = require("cors");
const multer = require("multer");

const uploadRoutes = require("./routes/uploadroutes");


const app = express();

const PORT = 5000;


app.use(cors());


app.use("/api/upload", uploadRoutes);


app.use((err, req, res, next) => {

    if (err instanceof multer.MulterError) {

        return res.status(400).json({
            success: false,
            message: err.message
        });
    }

    return res.status(400).json({
        success: false,
        message: err.message
    });
});


app.listen(PORT, () => {
    console.log(`Backend is running on port ${PORT}`);
});