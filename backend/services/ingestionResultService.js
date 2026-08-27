function createIngestionResult({
    file,
    format,
    sheetName = null,
    dataset,
    profile
}) {
    return {
        success: true,
        message: "Dataset uploaded and structured successfully",

        data: {
            sourceFile: {
                fileName: file.originalname,
                format: format,
                sizeBytes: file.size,
                sheetName: sheetName
            },

            dataset: {
                headers: dataset.headers,
                rows: dataset.rows,
                profile: profile
            },

            handoff: {
                status: "ready_for_validation"
            }
        }
    };
}

module.exports = {
    createIngestionResult
};