const returnForm = document.querySelector("#sale-return-form");
const returnEstimate = document.querySelector("#return-estimate");
const returnError = document.querySelector("#sale-return-error");
const returnInputs = [...document.querySelectorAll(".sale-return-quantity")];

function createReturnIdempotencyKey() {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
        return globalThis.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function updateReturnEstimate() {
    const estimate = returnInputs.reduce((total, input) => {
        const quantity = Number(input.value) || 0;
        const remaining = Number(input.dataset.remaining) || 0;
        const amount = Number(input.dataset.refund) || 0;
        if (quantity <= 0 || quantity > remaining || remaining <= 0) return total;
        return total + amount * quantity / remaining;
    }, 0);
    returnEstimate.textContent = `MWK ${estimate.toFixed(2)}`;
}

returnInputs.forEach((input) => input.addEventListener("input", updateReturnEstimate));

document.querySelector("#return-invoice")?.addEventListener("change", (event) => {
    if (event.currentTarget.value) {
        window.location.assign(`/sales/returns?invoice_id=${encodeURIComponent(event.currentTarget.value)}`);
    }
});

returnForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    returnError.textContent = "";
    const items = returnInputs
        .filter((input) => Number(input.value) > 0)
        .map((input) => ({
            sale_txn_id: Number(input.dataset.saleTxnId),
            quantity: input.value,
        }));
    if (!items.length) {
        returnError.textContent = "Enter a return quantity for at least one item.";
        return;
    }
    if (returnInputs.some((input) => Number(input.value) > Number(input.dataset.remaining))) {
        returnError.textContent = "A return quantity exceeds the available quantity.";
        return;
    }

    const confirmed = await window.appDialog.confirm(
        `Process this return for an estimated MWK ${returnEstimate.textContent.replace("MWK ", "")}?`,
        { title: "Confirm sale return", confirmText: "Process return" },
    );
    if (!confirmed) return;

    const button = document.querySelector("#process-sale-return");
    button.disabled = true;
    try {
        const response = await fetch("/sales/returns", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "Idempotency-Key": createReturnIdempotencyKey(),
            },
            body: JSON.stringify({
                invoice_id: Number(returnForm.dataset.invoiceId),
                refund_method: document.querySelector("#refund-method").value,
                items,
            }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Sale return could not be processed");
        await window.appDialog.alert(
            `Return processed. Refund: MWK ${Number(result.refund_amount).toFixed(2)}.`,
            { title: "Sale return complete" },
        );
        window.location.assign(`/sales/returns?invoice_id=${returnForm.dataset.invoiceId}`);
    } catch (error) {
        returnError.textContent = error.message;
        button.disabled = false;
    }
});

updateReturnEstimate();
