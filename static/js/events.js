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

function isEventEnded(endValue, startValue) {
    let value = endValue || startValue;
    if (!endValue && value && value.length > 10) {
        const timezone = value.slice(10).match(/(Z|[+-]\d{2}:\d{2})$/)?.[0] || "";
        value = `${value.slice(0, 10)}T23:59:59${timezone}`;
    }
    const end = value && value.length === 10
        ? parseLocalDate(`${value}T23:59:59`)
        : parseLocalDate(value);
    return Boolean(end && end.getTime() < Date.now());
}

function localDateTime(date, time, defaultTime) {
    if (!date) return null;
    const timeValue = time || defaultTime;
    const localDate = new Date(`${date}T${timeValue}`);
    const offsetMinutes = -localDate.getTimezoneOffset();
    const sign = offsetMinutes >= 0 ? "+" : "-";
    const absoluteOffset = Math.abs(offsetMinutes);
    const offset = `${sign}${String(Math.floor(absoluteOffset / 60)).padStart(2, "0")}:${String(absoluteOffset % 60).padStart(2, "0")}`;
    return `${date}T${timeValue}${offset}`;
}

function updateCountdown(startValue, endValue) {
    const target = parseLocalDate(startValue);
    const countdown = document.querySelector("#event-countdown-value");
    const label = document.querySelector("#event-countdown-label");
    const openPos = document.querySelector("#event-open-pos");
    const eventUnavailable = ["closed", "cancelled", "archived"]
        .includes(window.eventCardBeingOpened?.dataset.status);
    if (!target) {
        countdown.textContent = "Date not set";
        label.textContent = "";
        openPos.disabled = true;
        return;
    }

    const remaining = target.getTime() - Date.now();
    const expired = isEventEnded(endValue, startValue);
    if (remaining > 0) {
        const days = Math.floor(remaining / 86400000);
        const hours = Math.floor((remaining % 86400000) / 3600000);
        const minutes = Math.floor((remaining % 3600000) / 60000);
        countdown.textContent = `${days}d ${hours}h ${minutes}m`;
        label.textContent = "Until event";
        openPos.disabled = true;
    } else if (expired) {
        countdown.textContent = "Event passed";
        label.textContent = "";
        openPos.disabled = true;
    } else if (isEventToday(startValue)) {
        countdown.textContent = "Event day";
        label.textContent = "Open POS is available today";
        openPos.disabled = eventUnavailable;
    } else {
        countdown.textContent = "Event passed";
        label.textContent = "";
        openPos.disabled = true;
    }
}

window.openEventDetails = function (card) {
        window.eventCardBeingOpened = card;
        const start = parseLocalDate(card.dataset.start);
        const expired = ["closed", "cancelled", "archived"].includes(card.dataset.status)
            || isEventEnded(card.dataset.end, card.dataset.start);
        if (expired && !["closed", "cancelled", "archived"].includes(card.dataset.status)) {
            card.dataset.status = "closed";
            card.querySelector("em").textContent = "Closed";
        }
        document.querySelector("#event-detail-name").textContent = card.dataset.name;
        document.querySelector("#event-detail-venue").textContent = card.dataset.venue || "Location not set";
        document.querySelector("#event-detail-date").textContent = formatEventDate(card.dataset.start);
        document.querySelector("#event-detail-type").textContent =
            [card.dataset.type, card.dataset.status].filter(Boolean).join(" · ");
        document.querySelector("#event-detail-description").textContent =
            card.dataset.description || "No additional details.";
        document.querySelector("#event-view-sales").href = `/events/${card.dataset.id}`;
        const assignStock = document.querySelector("#assign-event-stock");
        const isClosed = ["closed", "cancelled", "archived"].includes(card.dataset.status);
        assignStock.disabled = isClosed || expired;
        document.querySelector("#event-open-pos").disabled = isClosed || expired;
        document.querySelector("#event-open-pos").onclick = () => {
            window.location.assign(`/sales/pos?event_id=${card.dataset.id}`);
        };

        document.querySelectorAll(".event-card").forEach((card) => {
            const dateLabel = card.querySelector("span");
            if (dateLabel) dateLabel.textContent = formatEventDate(card.dataset.start);
        });
        clearInterval(countdownTimer);
        updateCountdown(card.dataset.start, card.dataset.end);
        countdownTimer = setInterval(() => updateCountdown(card.dataset.start, card.dataset.end), 60000);
        if (eventDialog?.open) return;
        if (eventDialog?.showModal) eventDialog.showModal();
        else if (eventDialog) eventDialog.setAttribute("open", "");
};

document.querySelectorAll(".event-card").forEach((card) => {
    if (!["closed", "cancelled", "archived"].includes(card.dataset.status) && isEventEnded(card.dataset.end, card.dataset.start)) {
        card.dataset.status = "closed";
        const status = card.querySelector("em");
        if (status) status.textContent = "Closed";
    }
});

const eventGrid = document.querySelector("#events-grid");
const eventFilterTabs = [...document.querySelectorAll("[data-event-filter]")];
const noEventsInFilter = document.querySelector("#no-events-in-filter");

function filterEvents(filter) {
    let visibleCount = 0;
    document.querySelectorAll(".event-card").forEach((card) => {
        const status = card.dataset.status;
        const matches = filter === "all"
            || status === filter
            || (filter === "canceled" && ["cancelled", "closed"].includes(status));
        card.hidden = !matches;
        if (matches) visibleCount += 1;
    });
    noEventsInFilter.hidden = visibleCount > 0;
}

async function activateStartedEvents() {
    for (const card of document.querySelectorAll('.event-card[data-status="planned"]')) {
        const startsAt = parseLocalDate(card.dataset.start);
        if (!startsAt || startsAt > new Date()) continue;

        try {
            const response = await fetch(`/events/${encodeURIComponent(card.dataset.id)}/activate`, {
                method: "PATCH",
                credentials: "same-origin",
            });
            if (!response.ok) {
                const body = await response.json().catch(() => ({}));
                throw new Error(body.detail || "Could not update event status.");
            }
            const body = await response.json();
            if (body.status !== "active") continue;
            card.dataset.status = "active";
            card.querySelector("em").textContent = "Active";
            if (window.eventCardBeingOpened === card) {
                document.querySelector("#event-detail-type").textContent =
                    [card.dataset.type, "active"].filter(Boolean).join(" · ");
            }
            filterEvents(document.querySelector('[data-event-filter][aria-pressed="true"]')?.dataset.eventFilter || "all");
        } catch (error) {
            document.querySelector("#event-action-error").textContent = error.message;
        }
    }
}

eventFilterTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
        eventFilterTabs.forEach((filterTab) => {
            filterTab.setAttribute("aria-pressed", String(filterTab === tab));
        });
        filterEvents(tab.dataset.eventFilter);
    });
});

eventGrid?.addEventListener("click", async (event) => {
    const actionButton = event.target.closest("[data-event-action]");
    if (!actionButton) return;

    const eventCard = actionButton.closest(".event-card");
    const action = actionButton.dataset.eventAction;
    const eventName = eventCard.dataset.name;
    const confirmation = {
        delete: `Delete "${eventName}"? This cannot be undone.`,
        cancel: `Mark "${eventName}" as canceled?`,
        archive: `Archive "${eventName}"?`,
    }[action];
    if (!window.confirm(confirmation)) return;

    const actionError = document.querySelector("#event-action-error");
    actionError.textContent = "";
    actionButton.disabled = true;
    try {
        const response = await fetch(
            `/events/${encodeURIComponent(eventCard.dataset.id)}${action === "delete" ? "" : `/${action}`}`,
            {
                method: action === "delete" ? "DELETE" : "PATCH",
                credentials: "same-origin",
            },
        );
        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            throw new Error(body.detail || `Could not ${action} event.`);
        }
        window.location.reload();
    } catch (error) {
        actionError.textContent = error.message;
        actionButton.disabled = false;
    }
});

activateStartedEvents();
setInterval(activateStartedEvents, 30000);

document.querySelector("#close-event-dialog")?.addEventListener("click", () => eventDialog?.close());

const assignStockLink = document.querySelector("#assign-event-stock");
const assignStockDialog = document.querySelector("#assign-event-stock-dialog");
const assignStockForm = document.querySelector("#assign-event-stock-form");
const assignStockError = document.querySelector("#assign-event-stock-error");

assignStockLink?.addEventListener("click", (event) => {
    event.preventEventDefault?.();
    event.preventDefault();
    const currentCard = document.querySelector(".event-card:focus") || window.eventCardBeingOpened;
    document.querySelector("#assign-event-id").value = currentCard?.dataset.id || "";
    assignStockForm.reset();
    assignStockError.textContent = "";
    if (assignStockDialog?.showModal) assignStockDialog.showModal();
});

assignStockForm?.addEventListener("submit", async (event) => {
    if (event.submitter?.value !== "default") return;
    event.preventDefault();
    assignStockError.textContent = "";
    const allocations = [...assignStockForm.querySelectorAll("[data-item-id]")]
        .map((input) => ({
            item_id: Number(input.dataset.itemId),
            quantity: Number(input.value),
        }))
        .filter((allocation) => Number.isFinite(allocation.quantity) && allocation.quantity > 0);
    if (!allocations.length) {
        assignStockError.textContent = "Enter a quantity for at least one item.";
        return;
    }
    const eventId = document.querySelector("#assign-event-id").value;
    try {
        const response = await fetch(`/events/${encodeURIComponent(eventId)}/stock`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ allocations }),
        });
        if (!response.ok) {
            const body = await response.json();
            throw new Error(body.detail || "Could not assign event stock.");
        }
        assignStockDialog.close();
        window.location.reload();
    } catch (error) {
        assignStockError.textContent = error.message;
    }
});

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
            starts_at: localDateTime(startDate, startTime, "00:00"),
            ends_at: localDateTime(endDate, endTime, "23:59:59"),
            event_type: formData.get("event_type"),
            description: formData.get("description"),
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
