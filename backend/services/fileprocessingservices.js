// const fs = require("fs");
// const path = require("path");
// const { parse } = require("csv-parse/sync");
// const XLSX = require("xlsx");

// const SUPPORTED_EXTENSIONS = [".csv", ".xlsx", ".xls"];

// function processFile(file) {
//     if (!file || !file.path) {
//         throw new Error("Uploaded file information is missing");
//     }

//     const extension = path.extname(file.originalname).toLowerCase();

//     if (!SUPPORTED_EXTENSIONS.includes(extension)) {
//         throw new Error("Unsupported file format");
//     }

//     if (extension === ".csv") {
//         const content = fs.readFileSync(file.path, "utf8");

//         const records = parse(content, {
//             columns: true,
//             skip_empty_lines: true,
//             bom: true
//         });

//         return {
//             headers: records.length > 0 ? Object.keys(records[0]) : [],
//             rows: records
//         };
//     }

//     const workbook = XLSX.readFile(file.path);

//     const firstSheetName = workbook.SheetNames[0];

//     if (!firstSheetName) {
//         throw new Error("Excel file does not contain a worksheet");
//     }

//     const worksheet = workbook.Sheets[firstSheetName];

//     const records = XLSX.utils.sheet_to_json(worksheet, {
//         defval: null
//     });

//     return {
//         headers: records.length > 0 ? Object.keys(records[0]) : [],
//         rows: records
//     };
// }

// module.exports = {
//     processFile
// };

//the above code is combined version of all the code file formate,parce,process with limitaions 
// const {
//     detectFileFormat
// } = require("./fileformateservice");

// const {
//     parseCSV,
//     parseExcel
// } = require("./fileparsingservice");


// function isEmpty(value) {

//     return (
//         value === null ||
//         value === undefined ||
//         String(value).trim() === ""
//     );
// }


// function countValues(row) {

//     return row.filter(
//         (value) => !isEmpty(value)
//     ).length;
// }


// function getRowWidth(row) {

//     let lastValueIndex = -1;

//     for (let i = 0; i < row.length; i++) {

//         if (!isEmpty(row[i])) {
//             lastValueIndex = i;
//         }
//     }

//     return lastValueIndex + 1;
// }


// function findHeaderRow(rawRows) {

//     for (let i = 0; i < rawRows.length; i++) {

//         const row = rawRows[i];

//         // A single value is probably a title,
//         // not a table header.
//         if (countValues(row) < 2) {
//             continue;
//         }

//         const width = getRowWidth(row);

//         const possibleHeaders =
//             row.slice(0, width);

//         // Headers cannot contain empty cells.
//         const hasEmptyHeader =
//             possibleHeaders.some(isEmpty);

//         if (hasEmptyHeader) {
//             continue;
//         }


//         // Find the next non-empty row.
//         let nextRow = null;

//         for (
//             let j = i + 1;
//             j < rawRows.length;
//             j++
//         ) {

//             if (countValues(rawRows[j]) > 0) {

//                 nextRow = rawRows[j];
//                 break;
//             }
//         }


//         // A header without data is not useful.
//         if (!nextRow) {
//             continue;
//         }


//         const nextRowWidth =
//             getRowWidth(nextRow);


//         // If the next row is wider than this row,
//         // this row is probably a title/description.
//         if (nextRowWidth > width) {
//             continue;
//         }


//         return i;
//     }


//     return -1;
// }


// function validateHeaders(rawHeaders) {

//     const headers = rawHeaders.map(
//         (header) =>
//             String(header).trim()
//     );


//     if (
//         headers.some(
//             (header) => header === ""
//         )
//     ) {
//         throw new Error(
//             "Dataset contains an empty header"
//         );
//     }


//     const normalizedHeaders =
//         headers.map(
//             (header) =>
//                 header.toLowerCase()
//         );


//     const uniqueHeaders =
//         new Set(normalizedHeaders);


//     if (
//         uniqueHeaders.size !==
//         normalizedHeaders.length
//     ) {
//         throw new Error(
//             "Dataset contains duplicate headers"
//         );
//     }


//     return headers;
// }


// function normalizeData(rawRows) {

//     if (
//         !Array.isArray(rawRows) ||
//         rawRows.length === 0
//     ) {

//         throw new Error(
//             "Dataset is empty"
//         );
//     }


//     const headerIndex =
//         findHeaderRow(rawRows);


//     if (headerIndex === -1) {

//         throw new Error(
//             "No usable table could be found"
//         );
//     }

//     const headerRow =
//         rawRows[headerIndex];


//     const width =
//         getRowWidth(headerRow);


//     const headers =
//         validateHeaders(
//             headerRow.slice(0, width)
//         );


//     const rows = [];


//     for (
//         let i = headerIndex + 1;
//         i < rawRows.length;
//         i++
//     ) {

//         const rawRow = rawRows[i];


//         // Blank rows before data are ignored.
//         // Blank row after data means table ended.
//         if (countValues(rawRow) === 0) {

//             if (rows.length > 0) {
//                 break;
//             }

//             continue;
//         }


//         const extraValues =
//             rawRow
//                 .slice(width)
//                 .some(
//                     (value) =>
//                         !isEmpty(value)
//                 );


//         if (extraValues) {

//             throw new Error(
//                 `Row ${i + 1} contains more values than the headers`
//             );
//         }


//         const row = {};


//         headers.forEach(
//             (header, index) => {

//                 const value =
//                     rawRow[index];


//                 row[header] =
//                     isEmpty(value)
//                         ? null
//                         : value;
//             }
//         );


//         rows.push(row);
//     }


//     if (rows.length === 0) {

//         throw new Error(
//             "Dataset contains headers but no data rows"
//         );
//     }


//     return {
//         headers,
//         rows
//     };
// }


// function processFile(file) {

//     const format =
//         detectFileFormat(file);


//     if (format === "csv") {

//         const rawRows =
//             parseCSV(file.path);

//         return normalizeData(rawRows);
//     }


//     if (
//         format === "xlsx" ||
//         format === "xls"
//     ) {

//         const sheets =
//             parseExcel(file.path);


//         for (const rawRows of sheets) {

//             try {

//                 return normalizeData(
//                     rawRows
//                 );

//             } catch (error) {

//                 // This sheet was not usable.
//                 // Try the next one.
//             }
//         }


//         throw new Error(
//             "No usable table found in the Excel workbook"
//         );
//     }


//     throw new Error(
//         "Unsupported file format"
//     );
// }


// module.exports = {
//     processFile
// };

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
    if (!file || !file.originalname) {
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

    const sheets = [];

    for (const sheetName of workbook.SheetNames) {
        const sheet = workbook.Sheets[sheetName];

        const rows = XLSX.utils.sheet_to_json(sheet, {
            header: 1,
            defval: null,
            blankrows: true,
            raw: true
        });

        sheets.push(rows);
    }

    return sheets;
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

    const uniqueHeaders = new Set(normalizedHeaders);

    if (uniqueHeaders.size !== normalizedHeaders.length) {
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
            if (rows.length > 0) {
                break;
            }

            continue;
        }

        const extraValues = rawRow
            .slice(width)
            .some((value) => !isEmpty(value));

        if (extraValues) {
            throw new Error(
                `Row ${i + 1} contains more values than the headers`
            );
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
        throw new Error(
            "Dataset contains headers but no data rows"
        );
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
        return normalizeData(rawRows);
    }

    if (format === "xlsx" || format === "xls") {
        const sheets = parseExcel(file.path);

        for (const rawRows of sheets) {
            try {
                return normalizeData(rawRows);
            } catch (error) {
                // Try the next sheet
            }
        }

        throw new Error(
            "No usable table found in the Excel workbook"
        );
    }

    throw new Error("Unsupported file format");
}

module.exports = {
    processFile
};