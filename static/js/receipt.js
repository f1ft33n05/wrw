const paymentForm = document.querySelector("#receipt-payment-form");

if (paymentForm) {
    paymentForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorMessage = document.querySelector("#receipt-payment-error");
        const button = document.querySelector("#record-payment");
        errorMessage.textContent = "";
        button.disabled = true;

        const formData = new FormData(paymentForm);
        const payload = {
            invoice_id: Number(paymentForm.dataset.invoiceId),
            amount: Number(formData.get("amount")),
            payment_method: formData.get("payment_method"),
        };

        try {
            const response = await fetch("/sales/pay", {
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
            errorMessage.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    });
}
