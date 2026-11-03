document.querySelector("#category-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  try {
    const response = await fetch("/items/categories", {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error((await response.json()).detail || "Request failed");
    location.reload();
  } catch (error) {
    document.querySelector("#category-error").textContent = error.message;
  }
});
