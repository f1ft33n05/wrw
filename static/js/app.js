
const deleteDialog = document.querySelector("#user-delete-dialog");
const editDialog = document.querySelector("#user-edit-dialog");
const createDialog = document.querySelector("#user-create-dialog");
const deleteError = document.querySelector("#delete-user-error");
const editError = document.querySelector("#edit-user-error");
const createError = document.querySelector("#create-user-error");
const editForm = document.querySelector("#user-edit-form");
const createForm = document.querySelector("#user-create-form");
let selectedUserId;

document.querySelector("[data-add-user]").addEventListener("click", () => {
    createError.textContent = "";
    createForm.reset();
    createDialog.showModal();
});

document.querySelector("[data-cancel-create-user]").addEventListener("click", () => {
    createDialog.close();
});

createForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = document.querySelector("#create-user-submit");
    button.disabled = true;
    createError.textContent = "";
    try {
        const response = await fetch("/users/create", {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(Object.fromEntries(new FormData(createForm))),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `Create failed (${response.status})`);
        }
        createDialog.close();
        window.location.reload();
    } catch (error) {
        createError.textContent = error.message;
    } finally {
        button.disabled = false;
    }
});

document.querySelectorAll("[data-delete-user]").forEach((button) => {
    button.addEventListener("click", () => {
    selectedUserId = button.dataset.userId;
    document.querySelector("#delete-user-name").textContent = button.dataset.userName;
    deleteError.textContent = "";
    deleteDialog.showModal();
    });
});

document.querySelector("[data-cancel-delete]").addEventListener("click", () => {
    deleteDialog.close();
});

document.querySelectorAll("[data-edit-user]").forEach((button) => {
    button.addEventListener("click", () => {
    selectedUserId = button.dataset.userId;
    editForm.elements.namedItem("name").value = button.dataset.userName;
    editForm.elements.namedItem("username").value = button.dataset.userUsername;
    editForm.elements.namedItem("email").value = button.dataset.userEmail;
    editForm.elements.namedItem("phone").value = button.dataset.userPhone;
    editForm.elements.namedItem("role").value = button.dataset.userRole;
    editForm.elements.namedItem("password").value = "";
    editError.textContent = "";
    editDialog.showModal();
    });
});

document.querySelector("[data-cancel-edit]").addEventListener("click", () => {
    editDialog.close();
});

document.querySelector("#confirm-delete-user").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    deleteError.textContent = "";
    try {
    const response = await fetch(`/users/${encodeURIComponent(selectedUserId)}`, {
        method: "DELETE",
        credentials: "same-origin",
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `Delete failed (${response.status})`);
    }
    deleteDialog.close();
    window.location.reload();
    } catch (error) {
    deleteError.textContent = error.message;
    } finally {
    button.disabled = false;
    }
});

editForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = document.querySelector("#save-user-changes");
    button.disabled = true;
    editError.textContent = "";
    const payload = Object.fromEntries(new FormData(editForm));
    if (!payload.password) {
    delete payload.password;
    }
    try {
    const response = await fetch(`/users/${encodeURIComponent(selectedUserId)}`, {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `Update failed (${response.status})`);
    }
    editDialog.close();
    window.location.reload();
    } catch (error) {
    editError.textContent = error.message;
    } finally {
    button.disabled = false;
    }
});