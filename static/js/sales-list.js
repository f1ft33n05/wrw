const paymentDialog = document.createElement("dialog");
paymentDialog.innerHTML = `
  <article>
    <h3>Record invoice payment</h3>
    <form id="invoice-payment-form">
      <label>Amount <input name="amount" type="number" min="0.01" step="0.01" required></label>
      <label>Payment method
        <select name="payment_method">
          <option value="cash">Cash</option>
          <option value="card">Card</option>
          <option value="mobile money">Mobile money</option>
          <option value="bank transfer">Bank transfer</option>
        </select>
      </label>
      <p id="invoice-payment-error" role="alert"></p>
      <div class="grid">
        <button type="button" id="cancel-invoice-payment">Cancel</button>
        <button type="submit">Record payment</button>
      </div>
    </form>
  </article>
`;
document.body.append(paymentDialog);

document.querySelectorAll(".pay-invoice-button").forEach((button) => {
    button.addEventListener("click", () => {
        const form = paymentDialog.querySelector("#invoice-payment-form");
        form.dataset.invoiceId = button.dataset.invoiceId;
        form.elements.namedItem("amount").value = button.dataset.balance;
        paymentDialog.showModal();
    });
});

paymentDialog.querySelector("#cancel-invoice-payment").addEventListener("click", () => paymentDialog.close());
paymentDialog.querySelector("#invoice-payment-form").addEventListener("submit", async (event) => {
    event.preventEventDefault?.();
    event.preventDefault();
    const form = event.currentTarget;
    const error = paymentDialog.querySelector("#invoice-payment-error");
    error.textContent = "";
    try {
        const response = await fetch("/sales/pay", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                invoice_id: Number(form.dataset.invoiceId),
                amount: Number(form.elements.namedItem("amount").value),
                payment_method: form.elements.namedItem("payment_method").value,
            }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || "Payment could not be recorded");
        window.location.reload();
    } catch (paymentError) {
        error.textContent = paymentError.message;
    }
});

const salesTable = document.querySelector("#all-sales-table");
const saleRows = [...(salesTable?.querySelectorAll("[data-sale-row]") || [])];
const salesFilters = {
    customer: document.querySelector("#sales-filter-customer"),
    payment: document.querySelector("#sales-filter-payment"),
    event: document.querySelector("#sales-filter-event"),
    status: document.querySelector("#sales-filter-status"),
    from: document.querySelector("#sales-filter-from"),
    to: document.querySelector("#sales-filter-to"),
};
const emptySalesRow = salesTable?.querySelector("[data-sales-empty]");

function formatSalesTotal(cents) {
    return `${salesTable.dataset.currency} ${(cents / 100).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    })}`;
}

function updateSalesFilters() {
    const from = salesFilters.from.value;
    const to = salesFilters.to.value;
    let matchCount = 0;

    saleRows.forEach((row) => {
        const saleDate = /^\d{4}-\d{2}-\d{2}/.test(row.dataset.date)
            ? row.dataset.date.slice(0, 10)
            : "";
        const methods = row.dataset.paymentMethods.split("|").filter(Boolean);
        const matches = (!salesFilters.customer.value || row.dataset.customerId === salesFilters.customer.value)
            && (!salesFilters.payment.value || methods.includes(salesFilters.payment.value))
            && (!salesFilters.event.value || row.dataset.eventId === salesFilters.event.value)
            && (!salesFilters.status.value || row.dataset.status === salesFilters.status.value)
            && (!from || (saleDate && saleDate >= from))
            && (!to || (saleDate && saleDate <= to));

        row.dataset.filterMatch = String(matches);
        row.hidden = !matches;
        if (!matches) return;

        matchCount += 1;
    });

    if (emptySalesRow) emptySalesRow.hidden = matchCount > 0;
    salesTable?.dispatchEvent(new Event("tablefilterchange"));
    updateVisibleSalesTotals();
}

function updateVisibleSalesTotals() {
    const visibleRows = saleRows.filter((row) => !row.hidden);
    const totals = visibleRows.reduce((sum, row) => ({
        total: sum.total + Math.round(Number(row.dataset.total) * 100),
        paid: sum.paid + Math.round(Number(row.dataset.paid) * 100),
        balance: sum.balance + Math.round(Number(row.dataset.balance) * 100),
    }), { total: 0, paid: 0, balance: 0 });

    document.querySelector("#sales-total-count").textContent = visibleRows.length;
    document.querySelector("#sales-total-due").textContent = formatSalesTotal(totals.total);
    document.querySelector("#sales-total-paid").textContent = formatSalesTotal(totals.paid);
    document.querySelector("#sales-total-balance").textContent = formatSalesTotal(totals.balance);
}

document.querySelector("#sales-filters")?.addEventListener("submit", (event) => {
    event.preventDefault();
    updateSalesFilters();
});
Object.values(salesFilters).forEach((filter) => {
    filter?.addEventListener("change", updateSalesFilters);
});
salesTable?.addEventListener("tablepagerender", updateVisibleSalesTotals);

document.querySelector("#sales-filter-clear")?.addEventListener("click", () => {
    Object.values(salesFilters).forEach((filter) => {
        if (filter) filter.value = "";
    });
    updateSalesFilters();
});
