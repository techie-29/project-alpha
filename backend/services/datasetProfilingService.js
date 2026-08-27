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

    const yearFirst =
        /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/;

    const dayFirst =
        /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/;

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

function profileColumn(columnName, rows) {
    let missingCount = 0;

    const typeCounts = {
        number: 0,
        date: 0,
        text: 0
    };

    for (const row of rows) {
        const value = row[columnName];

        if (isMissing(value)) {
            missingCount++;
            continue;
        }

        const valueType = detectValueType(value);

        typeCounts[valueType]++;
    }

    const foundTypes = Object.keys(typeCounts).filter((type) => {
        return typeCounts[type] > 0;
    });

    let detectedType = "unknown";

    if (foundTypes.length === 1) {
        detectedType = foundTypes[0];
    }

    if (foundTypes.length > 1) {
        detectedType = "mixed";
    }

    return {
        name: columnName,
        detectedType: detectedType,
        missingCount: missingCount,
        nonMissingCount: rows.length - missingCount,
        hasMixedTypes: foundTypes.length > 1,
        typeCounts: typeCounts
    };
}

function profileDataset(dataset) {
    const headers = dataset.headers;
    const rows = dataset.rows;

   const columns = headers.map((header) => {
    return profileColumn(header, rows);
});

    return {
        rowCount: rows.length,
        columnCount: headers.length,
        columns: columns
    };
}

module.exports = {
    profileDataset
};