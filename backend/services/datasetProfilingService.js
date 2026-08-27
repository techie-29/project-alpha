function isMissing(value) {
    return (
        value === null ||
        value === undefined ||
        (typeof value === "string" && value.trim() === "")
    );
}

function isNumber(value) {
    if (typeof value === "number") {
        return Number.isFinite(value);
    }

    if (typeof value !== "string") {
        return false;
    }

    const cleanedValue = value.trim();

    return (
        cleanedValue !== "" &&
        Number.isFinite(Number(cleanedValue))
    );
}

function isDate(value) {
    if (value instanceof Date) {
        return !Number.isNaN(value.getTime());
    }

    if (typeof value !== "string") {
        return false;
    }

    const cleanedValue = value.trim();
    const yearFirst = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/;
    const dayFirst = /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/;

    let match = cleanedValue.match(yearFirst);
    let year;
    let month;
    let day;

    if (match) {
        year = Number(match[1]);
        month = Number(match[2]);
        day = Number(match[3]);
    } else {
        match = cleanedValue.match(dayFirst);

        if (!match) {
            return false;
        }

        day = Number(match[1]);
        month = Number(match[2]);
        year = Number(match[3]);
    }

    const date = new Date(Date.UTC(year, month - 1, day));

    return (
        date.getUTCFullYear() === year &&
        date.getUTCMonth() === month - 1 &&
        date.getUTCDate() === day
    );
}

function detectValueType(value) {
    if (isNumber(value)) {
        return "number";
    }

    if (isDate(value)) {
        return "date";
    }

    return "text";
}

function detectColumnType(columnName, rows) {
    const detectedTypes = new Set();

    for (const row of rows) {
        const value = row[columnName];

        if (!isMissing(value)) {
            detectedTypes.add(detectValueType(value));
        }
    }

    if (detectedTypes.size === 0) {
        return "unknown";
    }

    if (detectedTypes.size > 1) {
        return "mixed";
    }

    return Array.from(detectedTypes)[0];
}

function profileDataset(dataset) {
    const headers = dataset.headers;
    const rows = dataset.rows;

    const columns = headers.map((header) => {
        return {
            name: header,
            detectedType: detectColumnType(header, rows)
        };
    });

    return {
        rowCount: rows.length,
        columnCount: headers.length,
        columns
    };
}

module.exports = {
    profileDataset
};
