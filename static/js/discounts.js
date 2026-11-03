const typeSelect = document.querySelector("#discount-type");
const itemTarget = document.querySelector("#item-target");
const categoryTarget = document.querySelector("#category-target");

typeSelect.addEventListener("change", () => {
  const isItem = typeSelect.value === "item";
  itemTarget.hidden = !isItem;
  categoryTarget.hidden = isItem;
  itemTarget.querySelector("select").disabled = !isItem;
  categoryTarget.querySelector("select").disabled = isItem;
});

document.querySelector("#discount-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  data.target_id = Number(typeSelect.value === "item" ? data.target_id : data.category_target_id);
  data.percentage = Number(data.percentage);
  delete data.category_target_id;
  try {
    const response = await fetch("/items/discounts", {
      method: "POST",
      credentials: "same-origin",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error((await response.json()).detail || "Request failed");
    location.reload();
  } catch (error) {
    document.querySelector("#discount-error").textContent = error.message;
  }
});
