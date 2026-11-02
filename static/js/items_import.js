const form = document.querySelector("#item-import-form");
form.addEventListener("submit", async event => {
  event.preventDefault();
  document.querySelector("#import-error").textContent = "";
  try {
    const response = await fetch("/items/import", { method: "POST", credentials: "same-origin", body: new FormData(form) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || "Import failed");
    let message = `Imported: ${result.created} created, ${result.updated} updated, ${result.skipped} skipped.`;
    if (result.errors?.length) message += ` Errors: ${result.errors.join("; ")}`;
    document.querySelector("#import-result").textContent = message;
  } catch (error) { document.querySelector("#import-error").textContent = error.message; }
});
