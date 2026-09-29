const fs = require("fs");
const crypto = require("crypto");

async function hashFile(filePath) {
  if (!filePath) throw new Error("File path is required");

  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    const stream = fs.createReadStream(filePath);

    stream.on("error", reject);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("end", () => resolve(hash.digest("hex")));
  });
}

module.exports = { hashFile };
