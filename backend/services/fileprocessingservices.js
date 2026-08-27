const fs = require("fs");
const path = require("path");
const { parse } = require("csv-parse/sync");
const XLSX = require("xlsx");

const SUPPORTED_FORMATS = {
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".xls": "xls"
};

function detectFileFormat(file) {
    if (!file || !file.originalname || !file.path) {
        throw new Error("Uploaded file information is missing");
    }

    const extension = path.extname(file.originalname).toLowerCase();
    const format = SUPPORTED_FORMATS[extension];

    if (!format) {
        throw new Error("Unsupported file format");
    }

    return format;
}

function parseCSV(filePath) {
    const content = fs.readFileSync(filePath, "utf8");

    return parse(content, {
        bom: true,
        skip_empty_lines: false,
        relax_column_count: true
    });
}

function parseExcel(filePath) {
    const workbook = XLSX.readFile(filePath, {
        cellDates: true
    });

    return workbook.SheetNames.map((sheetName) => {
        const worksheet = workbook.Sheets[sheetName];

        const rows = XLSX.utils.sheet_to_json(worksheet, {
            header: 1,
            defval: null,
            blankrows: true,
            raw: true
        });

        return {
            sheetName,
            rows
        };
    });
}

function isEmpty(value) {
    return (
        value === null ||
        value === undefined ||
        String(value).trim() === ""
    );
}

function countValues(row) {
    return row.filter((value) => !isEmpty(value)).length;
}

function getRowWidth(row) {
    let lastValueIndex = -1;

    for (let i = 0; i < row.length; i++) {
        if (!isEmpty(row[i])) {
            lastValueIndex = i;
        }
    }

    return lastValueIndex + 1;
}

function findHeaderRow(rawRows) {
    for (let i = 0; i < rawRows.length; i++) {
        const row = rawRows[i];

        if (countValues(row) < 2) {
            continue;
        }

        const width = getRowWidth(row);
        const possibleHeaders = row.slice(0, width);

        if (possibleHeaders.some(isEmpty)) {
            continue;
        }

        let nextRow = null;

        for (let j = i + 1; j < rawRows.length; j++) {
            if (countValues(rawRows[j]) > 0) {
                nextRow = rawRows[j];
                break;
            }
        }

        if (!nextRow) {
            continue;
        }

        if (getRowWidth(nextRow) > width) {
            continue;
        }

        return i;
    }

    return -1;
}

function validateHeaders(rawHeaders) {
    const headers = rawHeaders.map((header) =>
        String(header).trim()
    );

    if (headers.some((header) => header === "")) {
        throw new Error("Dataset contains an empty header");
    }

    const normalizedHeaders = headers.map((header) =>
        header.toLowerCase()
    );

    if (new Set(normalizedHeaders).size !== normalizedHeaders.length) {
        throw new Error("Dataset contains duplicate headers");
    }

    return headers;
}

function normalizeData(rawRows) {
    if (!Array.isArray(rawRows) || rawRows.length === 0) {
        throw new Error("Dataset is empty");
    }

    const headerIndex = findHeaderRow(rawRows);

    if (headerIndex === -1) {
        throw new Error("No usable table could be found");
    }

    const headerRow = rawRows[headerIndex];
    const width = getRowWidth(headerRow);
    const headers = validateHeaders(headerRow.slice(0, width));
    const rows = [];

    for (let i = headerIndex + 1; i < rawRows.length; i++) {
        const rawRow = rawRows[i];

        if (countValues(rawRow) === 0) {
            continue;
        }

        const hasExtraValues = rawRow
            .slice(width)
            .some((value) => !isEmpty(value));

        if (hasExtraValues) {
            continue;
        }

        const row = {};

        headers.forEach((header, index) => {
            const value = rawRow[index];

            row[header] = isEmpty(value)
                ? null
                : value;
        });

        rows.push(row);
    }

    if (rows.length === 0) {
        throw new Error("Dataset contains headers but no data rows");
    }

    return {
        headers,
        rows
    };
}

function processFile(file) {
    const format = detectFileFormat(file);

    if (format === "csv") {
        const rawRows = parseCSV(file.path);
        const dataset = normalizeData(rawRows);

        return {
            format,
            sheetName: null,
            headers: dataset.headers,
            rows: dataset.rows
        };
    }

    const sheets = parseExcel(file.path);

    for (const sheet of sheets) {
        try {
            const dataset = normalizeData(sheet.rows);

            return {
                format,
                sheetName: sheet.sheetName,
                headers: dataset.headers,
                rows: dataset.rows
            };
        } catch (error) {
            // Continue until a usable worksheet is found.
        }
    }

    throw new Error("No usable table found in the Excel workbook");
}

module.exports = {
    processFile
};
