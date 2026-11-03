const eventForm = document.querySelector("#event-form");

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
