const express = require("express");
const router = express.Router();

const db = require("../config/db");
const {
  mapHeaders
} = require("../services/headerMappingService");


// POST /api/header-mapping/:ingestionId
router.post("/:ingestionId", async (req, res, next) => {
  const ingestionId = req.params.ingestionId;

  try {
    // 1. Load the ingestion headers
    const [ingestions] = await db.execute(
      `
      SELECT id, business_account_id, headers_json
      FROM ingestions
      WHERE id = ?
      `,
      [ingestionId]
    );

    if (ingestions.length === 0) {
      return res.status(404).json({
        success: false,
        message: "Ingestion not found"
      });
    }

    const ingestion = ingestions[0];

    // 2. Make sure this ingestion belongs to the logged-in business
    if (ingestion.business_account_id !== req.user.id) {
      return res.status(403).json({
        success: false,
        message: "You cannot access this ingestion"
      });
    }

    // 3. Convert stored JSON headers into a JavaScript array
    let headers = ingestion.headers_json;

    if (typeof headers === "string") {
      headers = JSON.parse(headers);
    }

    if (!Array.isArray(headers)) {
      return res.status(400).json({
        success: false,
        message: "Stored ingestion headers are invalid"
      });
    }

    // 4. Call Module 3 mapping service
    const mappings = mapHeaders(headers);

    // 5. Remove any old mappings for this ingestion
    await db.execute(
      `
      DELETE FROM header_mappings
      WHERE ingestion_id = ?
      `,
      [ingestionId]
    );

    // 6. Save the new mappings
    for (const mapping of mappings) {
      await db.execute(
        `
        INSERT INTO header_mappings (
          ingestion_id,
          original_header,
          mapped_header,
          mapping_status
        )
        VALUES (?, ?, ?, ?)
        `,
        [
          ingestionId,
          mapping.originalHeader,
          mapping.mappedHeader,
          mapping.mappingStatus
        ]
      );
    }

    // 7. Prepare summary
    const mappedCount = mappings.filter(
      (mapping) => mapping.mappingStatus === "mapped"
    ).length;

    const unmappedCount = mappings.length - mappedCount;

    // 8. Return Module 3 result
    return res.status(200).json({
      success: true,
      message: "Header mapping completed successfully",

      data: {
        ingestionId: Number(ingestionId),

        summary: {
          totalHeaders: mappings.length,
          mappedHeaders: mappedCount,
          unmappedHeaders: unmappedCount
        },

        mappings
      }
    });

  } catch (error) {
    next(error);
  }
});


module.exports = router;