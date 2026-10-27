const purchaseForm = document.querySelector("#purchase-form");
const purchaseLines = document.querySelector("#purchase-lines");
const purchaseLineTemplate = document.querySelector("#purchase-line-template");
const purchaseError = document.querySelector("#purchase-error");
const paymentMessage = document.querySelector("#supplier-payment-message");

function addPurchaseLine() {
    purchaseLines.append(purchaseLineTemplate.content.cloneNode(true));
}

document.querySelector("#add-purchase-line").addEventListener("click", addPurchaseLine);
purchaseLines.addEventListener("click", (event) => {
    if (event.target.matches("[data-remove-line]")) {
        event.target.closest("tr").remove();
    }
});
addPurchaseLine();

purchaseForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    purchaseError.textContent = "";
    const formData = new FormData(purchaseForm);
    const itemIds = formData.getAll("item_id");
    const quantities = formData.getAll("quantity");
    const unitCosts = formData.getAll("unit_cost");
    if (itemIds.length === 0 || itemIds.some((id) => !id)) {
        purchaseError.textContent = "Add at least one valid item.";
        return;
    }
    const payload = {
        supplier_id: Number(formData.get("supplier_id")),
        items: itemIds.map((itemId, index) => ({
            item_id: Number(itemId),
            quantity: Number(quantities[index]),
            unit_cost: Number(unitCosts[index]),
        })),
        amount_paid: Number(formData.get("amount_paid")),
        payment_method: formData.get("payment_method") || null,
    };
    try {
        const response = await fetch("/purchases/create", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `Purchase failed (${response.status})`);
        }
        window.location.reload();
    } catch (error) {
        purchaseError.textContent = error.message;
    }
});

document.querySelectorAll("[data-supplier-payment]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        paymentMessage.textContent = "";
        const formData = new FormData(form);
        const payload = {
            purchase_id: Number(form.dataset.purchaseId),
            amount: Number(formData.get("amount")),
            payment_method: formData.get("payment_method"),
        };
        try {
            const response = await fetch("/purchases/pay", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Payment failed (${response.status})`);
            }
            window.location.reload();
        } catch (error) {
            paymentMessage.textContent = error.message;
        }
    });
});
