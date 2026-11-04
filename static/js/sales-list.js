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
