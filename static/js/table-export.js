(() => {
    function cellText(cell) {
        return (cell.textContent || "").replace(/\s+/g, " ").trim();
    }

    function rowsFromTable(table, filtered) {
        return [...table.rows]
            .filter((row) => !filtered || row.dataset.filterMatch !== "false")
            .filter((row) => !(row.cells.length === 1 && row.cells[0].colSpan > 1))
            .map((row) => [...row.cells]
                .filter((cell) => !cell.hasAttribute("data-export-exclude"))
                .map(cellText))
            .filter((row) => row.length && row.some(Boolean));
    }

    function rowsFromElement(element, filtered) {
        if (element instanceof HTMLTableElement) return rowsFromTable(element, filtered);
        const rows = [];
        element.querySelectorAll("h1, h2, h3, p, table").forEach((part) => {
            if (part.closest("[data-export-exclude]")) return;
            if (part instanceof HTMLTableElement) {
                rows.push(...rowsFromTable(part, filtered));
            } else {
                const text = cellText(part);
                if (text) rows.push([text]);
            }
        });
        return rows;
    }

    function safeCell(value) {
        const text = String(value ?? "");
        return /^[\s]*[=+\-@]/.test(text) ? `'${text}` : text;
    }

    function download(content, mimeType, filename) {
        const url = URL.createObjectURL(new Blob([content], { type: mimeType }));
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        link.hidden = true;
        document.body.append(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    function exportCsv(rows, filename) {
        const csv = rows.map((row) => row.map((value) => {
            const text = safeCell(value);
            return `"${text.replace(/"/g, '""')}"`;
        }).join(",")).join("\r\n");
        download(`\uFEFF${csv}`, "text/csv;charset=utf-8", `${filename}.csv`);
    }

    function exportExcel(rows, filename) {
        const tableRows = rows.map((row) => (
            `<tr>${row.map((value) => `<td>${escapeHtml(safeCell(value))}</td>`).join("")}</tr>`
        )).join("");
        const workbook = `<!doctype html><html><head><meta charset="utf-8"></head><body><table>${tableRows}</table></body></html>`;
        download(workbook, "application/vnd.ms-excel;charset=utf-8", `${filename}.xls`);
    }

    function escapeHtml(value) {
        return value.replace(/[&<>"']/g, (character) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        })[character]);
    }

    document.addEventListener("click", (event) => {
        const button = event.target.closest("[data-export-action]");
        if (!button) return;
        const target = document.querySelector(button.dataset.exportTarget);
        if (!target) return;

        const filename = (button.dataset.exportName || document.title || "export")
            .trim()
            .replace(/[<>:"/\\|?*\x00-\x1f]/g, "-")
            .replace(/\s+/g, "_");
        if (button.dataset.exportAction === "print") {
            target.classList.add("table-export-print-target");
            document.body.classList.add("table-export-printing");
            const cleanup = () => {
                target.classList.remove("table-export-print-target");
                document.body.classList.remove("table-export-printing");
                window.removeEventListener("afterprint", cleanup);
            };
            window.addEventListener("afterprint", cleanup);
            window.print();
            return;
        }

        const rows = rowsFromElement(target, button.hasAttribute("data-export-filtered"));
        if (!rows.length) return;
        if (button.dataset.exportAction === "csv") exportCsv(rows, filename);
        if (button.dataset.exportAction === "excel") exportExcel(rows, filename);
    });
})();
