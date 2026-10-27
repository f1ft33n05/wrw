const contactForm = document.querySelector("#contact-create-form");

if (contactForm) {
    contactForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorMessage = document.querySelector("#contact-error");
        errorMessage.textContent = "";
        const formData = new FormData(contactForm);
        const payload = {
            name: formData.get("name"),
            email: formData.get("email") || null,
            phone: formData.get("phone") || null,
            address: formData.get("address") || null,
            outstanding_balance: 0,
            contact_type: contactForm.dataset.contactType,
        };
        try {
            const response = await fetch("/contacts/create", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Contact creation failed (${response.status})`);
            }
            window.location.reload();
        } catch (error) {
            errorMessage.textContent = error.message;
        }
    });
}

const editDialog = document.querySelector("#contact-edit-dialog");
const editForm = document.querySelector("#contact-edit-form");

if (editDialog && editForm) {
    document.querySelectorAll("[data-edit-contact]").forEach((button) => {
        button.addEventListener("click", () => {
            editForm.dataset.contactId = button.dataset.contactId;
            for (const field of ["name", "email", "phone", "address"]) {
                editForm.elements.namedItem(field).value =
                    button.dataset[`contact${field[0].toUpperCase()}${field.slice(1)}`] || "";
            }
            document.querySelector("#contact-edit-error").textContent = "";
            editDialog.showModal();
        });
    });

    document.querySelector("[data-cancel-contact-edit]").addEventListener("click", () => {
        editDialog.close();
    });

    editForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const errorMessage = document.querySelector("#contact-edit-error");
        errorMessage.textContent = "";
        const formData = new FormData(editForm);
        const payload = {
            name: formData.get("name"),
            email: formData.get("email") || null,
            phone: formData.get("phone") || null,
            address: formData.get("address") || null,
            contact_type: contactForm.dataset.contactType,
        };
        try {
            const response = await fetch(
                `/contacts/${encodeURIComponent(editForm.dataset.contactId)}`,
                {
                    method: "PUT",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                },
            );
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Contact update failed (${response.status})`);
            }
            window.location.reload();
        } catch (error) {
            errorMessage.textContent = error.message;
        }
    });
}

document.querySelectorAll("[data-delete-contact]").forEach((button) => {
    button.addEventListener("click", async () => {
        if (!window.confirm(`Delete ${button.dataset.contactName}?`)) {
            return;
        }
        try {
            const response = await fetch(
                `/contacts/${encodeURIComponent(button.dataset.contactId)}`,
                { method: "DELETE", credentials: "same-origin" },
            );
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `Contact delete failed (${response.status})`);
            }
            window.location.reload();
        } catch (error) {
            window.alert(error.message);
        }
    });
});
