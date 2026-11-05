const posForm = document.querySelector("#pos-form");
const itemSelection = document.querySelector("#item-selection");
const quantityInput = document.querySelector("#item-quantity");
const cartBody = document.querySelector("#cart-lines");
const posError = document.querySelector("#pos-error");
const cart = new Map();
let checkoutIdempotencyKey = null;
let checkoutIdempotencyPayload = null;

function createIdempotencyKey() {
    if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
        return globalThis.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function addProductCardToCart(card) {
        const option = itemSelection.querySelector(`option[value="${card.dataset.id}"]`);
        if (!option) return;

        const quantity = 1;
        const existing = cart.get(card.dataset.id);
        const newQuantity = quantity + (existing?.quantity || 0);
        const pricing = priceForQuantity(option, newQuantity);
        const stock = Number(card.dataset.stock);

        if (!Number.isFinite(pricing.totalUnitPrice) || pricing.totalUnitPrice <= 0) {
            posError.textContent = `${card.dataset.name} has no valid price.`;
            return;
        }
        if (newQuantity > stock) {
            posError.textContent = `Only ${stock} unit(s) are in stock.`;
            return;
        }

        cart.set(card.dataset.id, {
            name: card.dataset.name,
            quantity: newQuantity,
            unitPrices: pricing.unitPrices,
            priceBreakdown: pricing.priceBreakdown,
            lineTotal: pricing.lineTotal,
            discountPercentage: 0,
        });
        posError.textContent = "";
        renderCart();
}

document.querySelectorAll(".pos-product-card").forEach((card) => {
    card.addEventListener("click", () => addProductCardToCart(card));
});

const productSearch = document.querySelector("#pos-search");
const productCards = [...document.querySelectorAll(".pos-product-card")];

function findProductFromSearch(value) {
    const query = value.trim().toLowerCase();
    if (!query) return null;
    return productCards.find((card) =>
        card.dataset.id === query
        || card.dataset.barcode.toLowerCase() === query
        || card.dataset.name.toLowerCase() === query
    ) || productCards.find((card) =>
        card.dataset.name.toLowerCase().includes(query)
        || card.dataset.barcode.toLowerCase().includes(query)
    );
}

productSearch?.addEventListener("input", (event) => {
    const query = event.target.value.trim().toLowerCase();
    productCards.forEach((card) => {
        const matches = !query
            || card.dataset.name.toLowerCase().includes(query)
            || card.dataset.barcode.toLowerCase().includes(query);
        card.hidden = !matches;
    });
});

productSearch?.addEventListener("change", (event) => {
    const card = findProductFromSearch(event.target.value);
    if (card) addProductCardToCart(card);
});

productSearch?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const card = findProductFromSearch(event.currentTarget.value);
    if (card) {
        addProductCardToCart(card);
        event.currentTarget.value = "";
        productCards.forEach((productCard) => { productCard.hidden = false; });
    }
});

document.querySelector("#cancel-sale")?.addEventListener("click", () => {
    cart.clear();
    checkoutIdempotencyKey = null;
    checkoutIdempotencyPayload = null;
    renderCart();
});

function compactNumber(value) {
    return new Intl.NumberFormat("en-US", {
        maximumFractionDigits: 2,
    }).format(value);
}

function formatMoney(value) {
    return `MWK ${new Intl.NumberFormat("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(value)}`;
}

function priceForQuantity(option, quantity) {
    const threshold = Number(option.dataset.wholesaleThreshold);
    const thresholdIsValid = Number.isFinite(threshold) && threshold > 0;
    const wholesaleQuantity = thresholdIsValid
        ? Math.round(Math.floor((quantity / threshold) + Number.EPSILON) * threshold * 100) / 100
        : 0;
    const retailQuantity = quantity - wholesaleQuantity;
    const retailPrice = Number(option.dataset.retail);
    const wholesalePrice = Number(option.dataset.wholesale);
    const lineTotal =
        retailQuantity * (retailQuantity > 0 ? retailPrice : 0)
        + wholesaleQuantity * (wholesaleQuantity > 0 ? wholesalePrice : 0);
    const requestedDiscount = Number(document.querySelector("#item-discount")?.value || option.dataset.discount || 0);
    const safeDiscount = Number.isFinite(requestedDiscount) ? Math.min(Math.max(requestedDiscount, 0), 100) : 0;
    const discountedLineTotal = lineTotal * (1 - safeDiscount / 100);
    const roundedLineTotal = Math.round((discountedLineTotal + Number.EPSILON) * 100) / 100;
    const pricesAreValid =
        Number.isFinite(retailPrice) && retailPrice > 0
        && Number.isFinite(wholesalePrice) && wholesalePrice > 0;
    const priceBreakdown = [];
    if (wholesaleQuantity > 0) {
        priceBreakdown.push(
            `${compactNumber(wholesaleQuantity)} @ MWK ${compactNumber(wholesalePrice)}`,
        );
    }
    if (retailQuantity > 0) {
        priceBreakdown.push(
            `${compactNumber(retailQuantity)} @ MWK ${compactNumber(retailPrice)}`,
        );
    }
    return {
        priceBreakdown: priceBreakdown.join("; "),
        unitPrices: `MWK ${compactNumber(wholesalePrice)}:${compactNumber(retailPrice)}`,
        totalUnitPrice: pricesAreValid ? roundedLineTotal / quantity : Number.NaN,
        lineTotal: roundedLineTotal,
    };
}

function updateSelectedPrice() {
    const option = itemSelection.selectedOptions[0];
    const quantity = Number(quantityInput.value) +
        (option && option.value ? cart.get(option.value)?.quantity || 0 : 0);
    const { unitPrices } =
        option && option.value && Number.isFinite(quantity) && quantity > 0
            ? priceForQuantity(option, quantity)
            : { unitPrices: "" };
    document.querySelector("#selected-price").textContent =
        unitPrices || "-";
}

function renderCart() {
    cartBody.replaceChildren();
    let total = 0;
    // if (cart.size === 0) {
    //     const row = document.createElement("tr");
    //     const cell = document.createElement("td");
    //     cell.colSpan = 6;
    //     cell.textContent = "No items added.";
    //     row.append(cell);
    //     cartBody.append(row);
    // }

    for (const [itemId, line] of cart) {
        const row = document.createElement("tr");
        for (const value of [
            line.name,
            String(line.quantity),
            line.priceBreakdown,
            line.unitPrices,
            formatMoney(line.lineTotal),
        ]) {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.append(cell);
        }
        const actionCell = document.createElement("td");
        const removeButton = document.createElement("button");
        removeButton.type = "button";
        removeButton.textContent = "Remove";
        removeButton.addEventListener("click", () => {
            cart.delete(itemId);
            renderCart();
        });
        actionCell.append(removeButton);
        row.append(actionCell);
        cartBody.append(row);
        total += line.lineTotal;
    }
    document.querySelector("#sale-total").textContent = formatMoney(total);
    document.querySelector("#pos-payable-total")?.replaceChildren(formatMoney(total));
    const itemCount = [...cart.values()].reduce((sum, line) => sum + line.quantity, 0);
    const count = document.querySelector("#pos-item-count");
    if (count) count.textContent = compactNumber(itemCount);
    const tendered = Number(new FormData(posForm).get("amount_paid")) || 0;
    document.querySelector("#sale-change")?.replaceChildren(formatMoney(Math.max(tendered - total, 0)));
}

itemSelection.addEventListener("change", async () => {
    const option = itemSelection.selectedOptions[0];
    if (option?.value) {
        try {
            const response = await fetch(`/items/${option.value}/discount`, { credentials: "same-origin" });
            if (response.ok) option.dataset.discount = (await response.json()).percentage;
        } catch {}
    }
    updateSelectedPrice();
});
quantityInput.addEventListener("input", updateSelectedPrice);
document.querySelector("#item-discount").addEventListener("input", updateSelectedPrice);

document.querySelector("#add-to-cart").addEventListener("click", () => {
    posError.textContent = "";
    const option = itemSelection.selectedOptions[0];
    const quantity = Number(quantityInput.value);
    const existing = option && cart.get(option.value);
    const newQuantity = quantity + (existing?.quantity || 0);
    const pricing = option && priceForQuantity(option, newQuantity);
    const totalUnitPrice = pricing?.totalUnitPrice;
    const stock = option && Number(option.dataset.stock);
    if (!option || !option.value || !Number.isFinite(quantity) || quantity <= 0) {
        posError.textContent = "Select an item and enter a valid quantity.";
        return;
    }
    if (!Number.isFinite(totalUnitPrice) || totalUnitPrice <= 0) {
        posError.textContent = "This item has no valid price for the selected price list.";
        return;
    }
    if (newQuantity > stock) {
        posError.textContent = `Only ${stock} unit(s) are in stock.`;
        return;
    }
    cart.set(option.value, {
        name: option.dataset.name,
        quantity: newQuantity,
        unitPrices: pricing.unitPrices,
        priceBreakdown: pricing.priceBreakdown,
        lineTotal: pricing.lineTotal,
            discountPercentage: Number(document.querySelector("#item-discount").value || option.dataset.discount || 0),
        });
    renderCart();
});

async function checkoutSale(paymentMethod, payments = null) {
    posError.textContent = "";
    if (cart.size === 0) {
        posError.textContent = "Add at least one item to the sale.";
        return;
    }

    const button = document.querySelector("#complete-sale") || document.querySelector("#cash-pay");
    button.disabled = true;
    const formData = new FormData(posForm);
    const customerId = formData.get("customer_id");
    const eventId = formData.get("event_id");
    const amountPaidInput = posForm.elements.namedItem("amount_paid");
    const total = [...cart.values()].reduce(
        (sum, line) => sum + line.lineTotal,
        0,
    );
    const splitPayments = payments && payments.length > 0;
    const amountPaid = splitPayments ? 0 : total;
    if (amountPaidInput) amountPaidInput.value = String(amountPaid);
    if (amountPaid > 0 && !paymentMethod) {
        posError.textContent = "Choose a payment method for the amount collected.";
        button.disabled = false;
        return;
    }

    const payload = {
        customer_id: customerId ? Number(customerId) : null,
        event_id: eventId ? Number(eventId) : null,
        location: formData.get("location"),
        items: [...cart.entries()].map(([itemId, line]) => ({
            item_id: Number(itemId),
            quantity: line.quantity,
            discount_percentage: line.discountPercentage || undefined,
        })),
        amount_paid: amountPaid,
        payment_method: splitPayments ? null : paymentMethod,
    };
    const serializedPayload = JSON.stringify(payload);
    if (checkoutIdempotencyPayload !== serializedPayload) {
        checkoutIdempotencyPayload = serializedPayload;
        checkoutIdempotencyKey = createIdempotencyKey();
    }

    try {
        const response = await fetch("/sales/create", {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "Idempotency-Key": checkoutIdempotencyKey,
            },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `Sale failed (${response.status})`);
        }
        const result = await response.json();
        if (splitPayments) {
            for (const payment of payments) {
                const paymentResponse = await fetch("/sales/pay", {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        invoice_id: result.invoice_id,
                        amount: payment.amount,
                        payment_method: payment.method,
                    }),
                });
                if (!paymentResponse.ok) {
                    const body = await paymentResponse.json();
                    throw new Error(body.detail || "One split payment could not be recorded");
                }
            }
        }
        window.location.assign(result.receipt_url);
    } catch (error) {
        posError.textContent = error.message;
    } finally {
        button.disabled = false;
    }
}

async function saveDraft() {
    posError.textContent = "";
    if (cart.size === 0) {
        posError.textContent = "Add at least one item to save a draft.";
        return;
    }
    const formData = new FormData(posForm);
    const payload = {
        customer_id: formData.get("customer_id") ? Number(formData.get("customer_id")) : null,
        event_id: formData.get("event_id") ? Number(formData.get("event_id")) : null,
        location: formData.get("location") || "store",
        items: [...cart.entries()].map(([itemId, line]) => ({
            item_id: Number(itemId),
            quantity: line.quantity,
            discount_percentage: line.discountPercentage || undefined,
        })),
        amount_paid: 0,
        payment_method: null,
        save_draft: true,
    };
    const response = await fetch("/sales/create", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": createIdempotencyKey(),
        },
        body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Draft sale could not be saved");
    window.location.reload();
}

posForm.addEventListener("submit", (event) => {
    event.preventDefault();
});

document.querySelector("#cash-pay")?.addEventListener("click", () => checkoutSale("cash"));
document.querySelector("#card-pay")?.addEventListener("click", () => checkoutSale("card"));
document.querySelector("#save-sale")?.addEventListener("click", () => {
    saveDraft().catch((error) => { posError.textContent = error.message; });
});

const multiplePaymentDialog = document.querySelector("#multiple-payment-dialog");
const multiplePaymentRows = document.querySelector("#multiple-payment-rows");

function addMultiplePaymentRow(amount = "") {
    const row = document.createElement("div");
    row.className = "multiple-payment-row";
    row.innerHTML = `
        <select name="method">
            <option value="cash">Cash</option>
            <option value="card">Card</option>
            <option value="mobile money">Mobile money</option>
            <option value="bank transfer">Bank transfer</option>
        </select>
        <input name="amount" type="number" min="0.01" step="0.01" value="${amount}" required>
        <button type="button" class="remove-payment-row">Remove</button>
    `;
    row.querySelector(".remove-payment-row").addEventListener("click", () => {
        row.remove();
        updateMultiplePaymentRemaining();
    });
    row.querySelector("[name=amount]").addEventListener("input", updateMultiplePaymentRemaining);
    multiplePaymentRows.append(row);
    updateMultiplePaymentRemaining();
}

function multiplePaymentTotal() {
    return [...multiplePaymentRows.querySelectorAll("[name=amount]")]
        .reduce((sum, input) => sum + (Number(input.value) || 0), 0);
}

function saleTotal() {
    return [...cart.values()].reduce((sum, line) => sum + line.lineTotal, 0);
}

function updateMultiplePaymentRemaining() {
    document.querySelector("#multiple-payment-remaining").textContent =
        formatMoney(Math.max(saleTotal() - multiplePaymentTotal(), 0));
}

document.querySelector("#multiple-pay")?.addEventListener("click", () => {
    if (cart.size === 0) {
        posError.textContent = "Add at least one item to the sale.";
        return;
    }
    multiplePaymentRows.replaceChildren();
    addMultiplePaymentRow(saleTotal().toFixed(2));
    multiplePaymentDialog.showModal();
});

document.querySelector("#add-payment-row")?.addEventListener("click", () => addMultiplePaymentRow());
document.querySelector("#multiple-payment-form")?.addEventListener("submit", async (event) => {
    if (event.submitter?.value !== "default") return;
    event.preventDefault();
    const payments = [...multiplePaymentRows.querySelectorAll(".multiple-payment-row")].map((row) => ({
        method: row.querySelector("[name=method]").value,
        amount: Number(row.querySelector("[name=amount]").value),
    }));
    const totalPaid = payments.reduce((sum, payment) => sum + payment.amount, 0);
    const error = document.querySelector("#multiple-payment-error");
    error.textContent = "";
    if (!payments.length || payments.some((payment) => !Number.isFinite(payment.amount) || payment.amount <= 0)) {
        error.textContent = "Enter a valid amount for every payment.";
        return;
    }
    if (Math.abs(totalPaid - saleTotal()) > 0.01) {
        error.textContent = `Split payments must equal ${formatMoney(saleTotal())}.`;
        return;
    }
    multiplePaymentDialog.close();
    await checkoutSale("multiple", payments);
});

document.querySelectorAll(".resume-sale").forEach((button) => {
    button.addEventListener("click", async () => {
        let draftItems = [];
        try {
            draftItems = JSON.parse(button.dataset.items || "[]");
        } catch (error) {
            posError.textContent = "Could not read this saved sale.";
            return;
        }
        cart.clear();
        for (const line of draftItems) {
            const option = itemSelection.querySelector(`option[value="${line.item_id}"]`);
            if (!option) continue;
            const pricing = priceForQuantity(option, Number(line.quantity));
            cart.set(String(line.item_id), {
                name: line.name,
                quantity: Number(line.quantity),
                unitPrices: pricing.unitPrices,
                priceBreakdown: pricing.priceBreakdown,
                lineTotal: pricing.lineTotal,
                discountPercentage: Number(line.discount_percentage || 0),
            });
        }
        const customer = posForm.elements.namedItem("customer_id");
        const event = posForm.elements.namedItem("event_id");
        if (customer) customer.value = button.dataset.customerId;
        if (event) event.value = button.dataset.eventId;
        const response = await fetch(`/sales/draft/${button.dataset.draftId}`, {
            method: "DELETE",
            credentials: "same-origin",
        });
        if (!response.ok) {
            posError.textContent = "The sale could not be resumed. Please try again.";
            return;
        }
        renderCart();
        button.remove();
    });
});

posForm.elements.namedItem("amount_paid").addEventListener("input", renderCart);
renderCart();
updateSelectedPrice();
