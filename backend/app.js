const express = require("express");
const multer = require("multer");
const app = express();
const port = 5000;
const upload = multer({
    dest:"uploads/"
});
app.post("/api/upload",
    upload.single("file"),(req,res)=>{
        res.json({
            message:"file received succesfull",
            file:req.file
        });
    }
);                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           ,
app.listen(port,()=>{
console.log(`Backend is running on port :${port}`)
});