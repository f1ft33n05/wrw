const posForm = document.querySelector("#pos-form");
const itemSelection = document.querySelector("#item-selection");
const quantityInput = document.querySelector("#item-quantity");
const cartBody = document.querySelector("#cart-lines");
const posError = document.querySelector("#pos-error");
const cart = new Map();

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
    const wholesaleQuantity = quantity >= threshold ? threshold : 0;
    const retailQuantity = quantity - wholesaleQuantity;
    const retailPrice = Number(option.dataset.retail);
    const wholesalePrice = Number(option.dataset.wholesale);
    const lineTotal =
        retailQuantity * (retailQuantity > 0 ? retailPrice : 0)
        + wholesaleQuantity * (wholesaleQuantity > 0 ? wholesalePrice : 0);
    const roundedLineTotal = Math.round((lineTotal + Number.EPSILON) * 100) / 100;
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
    if (cart.size === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 6;
        cell.textContent = "No items added.";
        row.append(cell);
        cartBody.append(row);
    }

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
    const tendered = Number(new FormData(posForm).get("amount_paid")) || 0;
    document.querySelector("#sale-change").textContent =
        formatMoney(Math.max(tendered - total, 0));
}

itemSelection.addEventListener("change", updateSelectedPrice);
quantityInput.addEventListener("input", updateSelectedPrice);

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
    });
    renderCart();
});

posForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    posError.textContent = "";
    if (cart.size === 0) {
        posError.textContent = "Add at least one item to the sale.";
        return;
    }

    const button = document.querySelector("#complete-sale");
    button.disabled = true;
    const formData = new FormData(posForm);
    const customerId = formData.get("customer_id");
    const amountPaid = Number(formData.get("amount_paid"));
    const total = [...cart.values()].reduce(
        (sum, line) => sum + line.lineTotal,
        0,
    );
    const paymentMethod = formData.get("payment_method");
    if (amountPaid > 0 && !paymentMethod) {
        posError.textContent = "Choose a payment method for the amount collected.";
        button.disabled = false;
        return;
    }

    const payload = {
        customer_id: customerId ? Number(customerId) : null,
        location: formData.get("location"),
        items: [...cart.entries()].map(([itemId, line]) => ({
            item_id: Number(itemId),
            quantity: line.quantity,
        })),
        amount_paid: amountPaid,
        payment_method: paymentMethod || null,
    };

    try {
        const response = await fetch("/sales/create", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `Sale failed (${response.status})`);
        }
        const result = await response.json();
        window.location.assign(result.receipt_url);
    } catch (error) {
        posError.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

posForm.elements.namedItem("amount_paid").addEventListener("input", renderCart);
renderCart();
updateSelectedPrice();
