const documentForm = document.querySelector("#document-form");
const lineBody = document.querySelector("#document-lines");
const lineTemplate = document.querySelector("#document-line-template");
const money = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function addDocumentLine() {
    lineBody.append(lineTemplate.content.cloneNode(true));
    updateTotals();
}

function updateTotals() {
    let subtotal = 0;
    lineBody.querySelectorAll("tr").forEach((row) => {
        const quantity = Number(row.querySelector('[name="quantity"]').value) || 0;
        const price = Number(row.querySelector('[name="unit_price"]').value) || 0;
        const discount = Number(row.querySelector('[name="discount_percentage"]').value) || 0;
        const total = quantity * price * (1 - Math.min(discount, 100) / 100);
        row.querySelector(".document-line-total").textContent = `MWK ${money.format(total)}`;
        subtotal += total;
    });
    const documentDiscount = Number(documentForm.elements.namedItem("discount_amount").value) || 0;
    const taxRate = Number(documentForm.elements.namedItem("tax_rate").value) || 0;
    const taxable = Math.max(subtotal - documentDiscount, 0);
    const tax = taxable * taxRate / 100;
    document.querySelector("#document-subtotal").textContent = `MWK ${money.format(subtotal)}`;
    document.querySelector("#document-tax").textContent = `MWK ${money.format(tax)}`;
    document.querySelector("#document-total").textContent = `MWK ${money.format(taxable + tax)}`;
}

if (documentForm) {
    const issueDate = documentForm.elements.namedItem("issue_date");
    issueDate.value = new Date().toISOString().slice(0, 10);
    document.querySelector("#add-document-line").addEventListener("click", addDocumentLine);
    lineBody.addEventListener("input", updateTotals);
    lineBody.addEventListener("change", (event) => {
        if (event.target.matches('[name="item_id"]')) {
            const option = event.target.selectedOptions[0];
            const row = event.target.closest("tr");
            row.querySelector('[name="description"]').value = option.dataset.name || "";
            row.querySelector('[name="unit_price"]').value = option.dataset.price || "";
        }
        updateTotals();
    });
    lineBody.addEventListener("click", (event) => {
        if (event.target.matches("[data-remove-document-line]")) {
            event.target.closest("tr").remove();
            updateTotals();
        }
    });
    documentForm.addEventListener("input", updateTotals);
    addDocumentLine();

    documentForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const error = document.querySelector("#document-error");
        error.textContent = "";
        const formData = new FormData(documentForm);
        const type = documentForm.dataset.documentType;
        const lines = [...lineBody.querySelectorAll("tr")].map((row) => ({
            item_id: row.querySelector('[name="item_id"]').value ? Number(row.querySelector('[name="item_id"]').value) : null,
            description: row.querySelector('[name="description"]').value,
            quantity: Number(row.querySelector('[name="quantity"]').value),
            unit_price: Number(row.querySelector('[name="unit_price"]').value),
            discount_percentage: Number(row.querySelector('[name="discount_percentage"]').value) || 0,
        }));
        const payload = {
            customer_id: Number(formData.get("customer_id")),
            issue_date: formData.get("issue_date"),
            notes: formData.get("notes") || null,
            tax_rate: Number(formData.get("tax_rate")) || 0,
            discount_amount: Number(formData.get("discount_amount")) || 0,
            currency: formData.get("currency"),
            lines,
            [type === "quotation" ? "expiry_date" : "due_date"]: formData.get(type === "quotation" ? "expiry_date" : "due_date") || null,
        };
        try {
            const response = await fetch(`/${type}s`, {
                method: "POST", credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const result = await response.json();
                throw new Error(result.detail || "Could not save document.");
            }
            const result = await response.json();
            window.location.assign(result.print_url);
        } catch (cause) {
            error.textContent = cause.message;
        }
    });
}

document.querySelectorAll("[data-convert-quotation]").forEach((button) => {
    button.addEventListener("click", async () => {
        const response = await fetch(`/quotations/${button.dataset.convertQuotation}/convert`, {
            method: "POST", credentials: "same-origin",
        });
        if (!response.ok) return;
        const result = await response.json();
        window.location.assign(result.print_url);
    });
});
