const eventForm = document.querySelector("#event-form");
const eventDialog = document.querySelector("#event-detail-dialog");
let countdownTimer = null;

function parseLocalDate(value) {
    if (!value) return null;
    const parsed = new Date(value.length === 10 ? `${value}T00:00:00` : value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function formatEventDate(value) {
    const date = parseLocalDate(value);
    if (!date) return "Date not set";
    return new Intl.DateTimeFormat(undefined, {
        weekday: "long",
        month: "long",
        day: "numeric",
    }).format(date);
}

function isEventToday(startValue) {
    const start = parseLocalDate(startValue);
    if (!start) return false;
    const today = new Date();
    return start.getFullYear() === today.getFullYear()
        && start.getMonth() === today.getMonth()
        && start.getDate() === today.getDate();
}

function updateCountdown(startValue) {
    const target = parseLocalDate(startValue);
    const countdown = document.querySelector("#event-countdown-value");
    const label = document.querySelector("#event-countdown-label");
    const openPos = document.querySelector("#event-open-pos");
    if (!target) {
        countdown.textContent = "Date not set";
        label.textContent = "";
        openPos.disabled = true;
        return;
    }

    const remaining = target.getTime() - Date.now();
    if (remaining > 0) {
        const days = Math.floor(remaining / 86400000);
        const hours = Math.floor((remaining % 86400000) / 3600000);
        const minutes = Math.floor((remaining % 3600000) / 60000);
        countdown.textContent = `${days}d ${hours}h ${minutes}m`;
        label.textContent = "Until event";
        openPos.disabled = true;
    } else if (isEventToday(startValue)) {
        countdown.textContent = "Event day";
        label.textContent = "Open POS is available today";
        openPos.disabled = false;
    } else {
        countdown.textContent = "Event passed";
        label.textContent = "";
        openPos.disabled = true;
    }
}

window.openEventDetails = function (card) {
        const start = parseLocalDate(card.dataset.start);
        document.querySelector("#event-detail-name").textContent = card.dataset.name;
        document.querySelector("#event-detail-venue").textContent = card.dataset.venue || "Location not set";
        document.querySelector("#event-detail-date").textContent = formatEventDate(card.dataset.start);
        document.querySelector("#event-detail-type").textContent =
            [card.dataset.type, card.dataset.status].filter(Boolean).join(" · ");
        document.querySelector("#event-detail-description").textContent =
            card.dataset.description || "No additional details.";
        document.querySelector("#event-view-sales").href = `/events/${card.dataset.id}`;
        document.querySelector("#event-open-pos").onclick = () => {
            window.location.assign(`/sales/pos?event_id=${card.dataset.id}`);
        };

        document.querySelectorAll(".event-card").forEach((card) => {
            const dateLabel = card.querySelector("span");
            if (dateLabel) dateLabel.textContent = formatEventDate(card.dataset.start);
        });
        clearInterval(countdownTimer);
        updateCountdown(card.dataset.start);
        countdownTimer = setInterval(() => updateCountdown(card.dataset.start), 60000);
        if (eventDialog?.open) return;
        if (eventDialog?.showModal) eventDialog.showModal();
        else if (eventDialog) eventDialog.setAttribute("open", "");
};

document.querySelector("#close-event-dialog")?.addEventListener("click", () => eventDialog?.close());

if (eventForm) {
    eventForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const error = document.querySelector("#event-error");
        error.textContent = "";
        const formData = new FormData(eventForm);
        const startDate = formData.get("starts_at_date");
        const endDate = formData.get("ends_at_date");
        const startTime = formData.get("starts_at_time");
        const endTime = formData.get("ends_at_time");
        const payload = {
            name: formData.get("name"),
            venue: formData.get("venue"),
            starts_at: startDate ? `${startDate}${startTime ? `T${startTime}` : ""}` : null,
            ends_at: endDate ? `${endDate}${endTime ? `T${endTime}` : ""}` : null,
            event_type: formData.get("event_type"),
            description: formData.get("description"),
            status: formData.get("status"),
        };
        try {
            const response = await fetch("/events", {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            if (!response.ok) {
                const body = await response.json();
                throw new Error(body.detail || "Could not create event.");
            }
            window.location.reload();
        } catch (cause) {
            error.textContent = cause.message;
        }
    });
}
