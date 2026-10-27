const allocationForm = document.querySelector("#allocation-form");
const allocationLines = document.querySelector("#allocation-lines");
const allocationTemplate = document.querySelector("#allocation-line-template");

if (allocationForm) {
    function addAllocationLine() {
        allocationLines.append(allocationTemplate.content.cloneNode(true));
    }

    document.querySelector("#add-allocation-line").addEventListener("click", addAllocationLine);
    allocationLines.addEventListener("click", (event) => {
        if (event.target.matches("[data-remove-allocation-line]")) {
            event.target.closest("tr").remove();
        }
    });
    addAllocationLine();

    allocationForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorMessage = document.querySelector("#allocation-error");
        errorMessage.textContent = "";
        const formData = new FormData(allocationForm);
        const itemIds = formData.getAll("item_id");
        const quantities = formData.getAll("quantity");
        const prices = formData.getAll("unit_price");
        if (itemIds.length === 0 || itemIds.some((id) => !id)) {
            errorMessage.textContent = "Add at least one valid item.";
            return;
        }
        try {
            const response = await fetch("/reseller_pg/allocations", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    reseller_id: Number(allocationForm.dataset.resellerId),
                    items: itemIds.map((itemId, index) => ({
                        item_id: Number(itemId),
                        quantity: Number(quantities[index]),
                        unit_price: Number(prices[index]),
                    })),
                }),
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Allocation failed (${response.status})`);
            }
            window.location.reload();
        } catch (error) {
            errorMessage.textContent = error.message;
        }
    });
}

const reconciliationForm = document.querySelector("#reconciliation-form");
if (reconciliationForm) {
    reconciliationForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorMessage = document.querySelector("#reconciliation-error");
        errorMessage.textContent = "";
        const linesById = new Map();
        document.querySelectorAll("[data-reconcile-line]").forEach((input) => {
            const lineId = input.dataset.reconcileLine;
            const line = linesById.get(lineId) || {
                allocation_line_id: Number(lineId),
                quantity_sold: 0,
                quantity_returned: 0,
            };
            if (input.dataset.reconcileField === "sold") {
                line.quantity_sold = Number(input.value);
            } else {
                line.quantity_returned = Number(input.value);
            }
            linesById.set(lineId, line);
        });
        const payload = {
            reseller_id: Number(reconciliationForm.dataset.resellerId),
            period: new FormData(reconciliationForm).get("period"),
            lines: [...linesById.values()].filter(
                (line) => line.quantity_sold > 0 || line.quantity_returned > 0,
            ),
        };
        try {
            const response = await fetch("/reseller_pg/reconcile", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Reconciliation failed (${response.status})`);
            }
            window.location.reload();
        } catch (error) {
            errorMessage.textContent = error.message;
        }
    });
}

const resellerPaymentForm = document.querySelector("#reseller-payment-form");
if (resellerPaymentForm) {
    resellerPaymentForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorMessage = document.querySelector("#reseller-payment-error");
        errorMessage.textContent = "";
        const formData = new FormData(resellerPaymentForm);
        try {
            const response = await fetch("/reseller_pg/pay", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    reseller_id: Number(resellerPaymentForm.dataset.resellerId),
                    amount: Number(formData.get("amount")),
                    payment_method: formData.get("payment_method"),
                }),
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Payment failed (${response.status})`);
            }
            window.location.reload();
        } catch (error) {
            errorMessage.textContent = error.message;
        }
    });
}
