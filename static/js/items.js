const createForm = document.querySelector("#item-create-form");
const editDialog = document.querySelector("#item-edit-dialog");
const editForm = document.querySelector("#item-edit-form");
const stockDialog = document.querySelector("#stock-dialog");
const stockForm = document.querySelector("#stock-form");
let editingId = null;
let stockItemId = null;

function payload(form) {
  const data = Object.fromEntries(new FormData(form));
  for (const field of ["purchase_price", "selling_price_wholesale", "selling_price_retail", "wholesale_threshold", "quantity"]) {
    if (field in data) data[field] = Number(data[field]);
  }
  data.category_id = data.category_id ? Number(data.category_id) : null;
  return data;
}

async function api(url, options = {}) {
  const response = await fetch(url, { credentials: "same-origin", ...options });
  if (!response.ok) { let body; try { body = await response.json(); } catch {} throw new Error(body?.detail || `Request failed (${response.status})`); }
  if (response.status !== 204) return response.json();
}

createForm.addEventListener("submit", async event => {
  event.preventDefault();
  try { await api("/items/create", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload(createForm)) }); location.reload(); }
  catch (error) { document.querySelector("#item-create-error").textContent = error.message; }
});

document.querySelectorAll("[data-edit-item]").forEach(button => button.addEventListener("click", () => {
  editingId = button.dataset.id;
  editForm.elements.namedItem("name").value = button.dataset.name;
  editForm.elements.namedItem("barcode").value = button.dataset.barcode;
  editForm.elements.namedItem("description").value = button.dataset.description;
  editForm.elements.namedItem("unit").value = button.dataset.unit;
  editForm.elements.namedItem("quantity").value = button.dataset.quantity;
  editForm.elements.namedItem("purchase_price").value = button.dataset.purchase;
  editForm.elements.namedItem("selling_price_wholesale").value = button.dataset.wholesale;
  editForm.elements.namedItem("selling_price_retail").value = button.dataset.retail;
  editForm.elements.namedItem("wholesale_threshold").value = button.dataset.threshold;
  editForm.elements.namedItem("category_id").value = button.dataset.category;
  editDialog.showModal();
}));
document.querySelector("[data-cancel-item-edit]").addEventListener("click", () => editDialog.close());
editForm.addEventListener("submit", async event => {
  event.preventDefault();
  try { await api(`/items/${editingId}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload(editForm)) }); location.reload(); }
  catch (error) { document.querySelector("#item-edit-error").textContent = error.message; }
});

document.querySelectorAll("[data-add-stock]").forEach(button => button.addEventListener("click", () => { stockItemId = button.dataset.addStock; stockDialog.showModal(); }));
document.querySelector("[data-cancel-stock]").addEventListener("click", () => stockDialog.close());
stockForm.addEventListener("submit", async event => {
  event.preventEventDefault?.();
  event.preventDefault();
  try { await api(`/items/adjust-stock/${stockItemId}`, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ quantity: Number(stockForm.elements.namedItem("quantity").value), reason: stockForm.elements.namedItem("reason").value }) }); location.reload(); }
  catch (error) { document.querySelector("#stock-error").textContent = error.message; }
});

document.querySelectorAll("[data-delete-item]").forEach(button => button.addEventListener("click", async () => {
  if (!confirm("Delete this item?")) return;
  try { await api(`/items/${button.dataset.deleteItem}`, { method: "DELETE" }); location.reload(); }
  catch (error) { alert(error.message); }
}));
