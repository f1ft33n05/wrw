(() => {
    const queue = [];
    let activeRequest = null;
    let dialog = null;
    let titleElement = null;
    let messageElement = null;
    let cancelButton = null;
    let confirmButton = null;

    function ensureDialog() {
        if (dialog) return;

        dialog = document.createElement("dialog");
        dialog.className = "app-confirm-dialog";
        dialog.setAttribute("aria-labelledby", "app-confirm-dialog-title");
        dialog.setAttribute("aria-describedby", "app-confirm-dialog-message");

        const article = document.createElement("article");
        titleElement = document.createElement("h2");
        titleElement.id = "app-confirm-dialog-title";
        messageElement = document.createElement("p");
        messageElement.id = "app-confirm-dialog-message";

        const actions = document.createElement("div");
        actions.className = "app-confirm-dialog-actions";
        cancelButton = document.createElement("button");
        cancelButton.type = "button";
        cancelButton.className = "secondary";
        cancelButton.textContent = "Cancel";
        confirmButton = document.createElement("button");
        confirmButton.type = "button";
        confirmButton.className = "app-confirm-dialog-confirm";

        actions.append(cancelButton, confirmButton);
        article.append(titleElement, messageElement, actions);
        dialog.append(article);
        document.body.append(dialog);

        cancelButton.addEventListener("click", () => dialog.close("cancel"));
        confirmButton.addEventListener("click", () => dialog.close("confirm"));
        dialog.addEventListener("close", () => {
            const request = activeRequest;
            activeRequest = null;
            if (request) request.resolve(dialog.returnValue === "confirm");
            showNext();
        });
    }

    function showNext() {
        if (activeRequest || queue.length === 0) return;
        ensureDialog();
        activeRequest = queue.shift();
        titleElement.textContent = activeRequest.title;
        messageElement.textContent = activeRequest.message;
        cancelButton.hidden = activeRequest.kind === "alert";
        confirmButton.textContent = activeRequest.confirmText;
        confirmButton.classList.toggle("secondary", !activeRequest.danger);
        confirmButton.classList.toggle("app-confirm-dialog-danger", activeRequest.danger);
        dialog.showModal();
        confirmButton.focus();
    }

    function open(kind, message, options = {}) {
        return new Promise((resolve) => {
            queue.push({
                kind,
                message: String(message),
                title: options.title || (kind === "alert" ? "Notice" : "Confirm action"),
                confirmText: options.confirmText || (kind === "alert" ? "OK" : "Confirm"),
                danger: Boolean(options.danger),
                resolve,
            });
            showNext();
        });
    }

    window.appDialog = {
        alert: (message, options) => open("alert", message, options),
        confirm: (message, options) => open("confirm", message, options),
    };
})();
