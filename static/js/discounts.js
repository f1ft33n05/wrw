const typeSelect = document.querySelector("#discount-type");
const itemTarget = document.querySelector("#item-target");
const categoryTarget = document.querySelector("#category-target");
const customerTarget = document.querySelector("#customer-target");

function updateDiscountTarget() {
  const targets = {
    item: itemTarget,
    category: categoryTarget,
    customer: customerTarget,
  };
  Object.entries(targets).forEach(([type, target]) => {
    const active = typeSelect.value === type;
    target.hidden = !active;
    target.querySelector("select").disabled = !active;
  });
}

typeSelect.addEventListener("change", updateDiscountTarget);
updateDiscountTarget();

document.querySelector("#discount-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  const targetField = {
    item: "target_id",
    category: "category_target_id",
    customer: "customer_target_id",
  }[typeSelect.value];
  data.target_id = Number(data[targetField]);
  data.percentage = Number(data.percentage);
  delete data.category_target_id;
  delete data.customer_target_id;
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
