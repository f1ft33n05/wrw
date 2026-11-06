const createForm = document.querySelector("#item-create-form");
const editDialog = document.querySelector("#item-edit-dialog");
const editForm = document.querySelector("#item-edit-form");
const stockDialog = document.querySelector("#stock-dialog");
const stockForm = document.querySelector("#stock-form");
let editingId = null;
let stockItemId = null;

const detailsDialog = document.querySelector("#item-details-view-dialog");
const detailsError = document.querySelector("#item-details-error");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  })[character]);
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function emptyRow(columnCount, message) {
  return `<tr><td colspan="${columnCount}">${escapeHtml(message)}</td></tr>`;
}

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

if (createForm) {
  createForm.addEventListener("submit", async event => {
    event.preventEventDefault?.();
    event.preventDefault();
    try { await api("/items/create", { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload(createForm)) }); location.reload(); }
    catch (error) { document.querySelector("#item-create-error").textContent = error.message; }
  });
}

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
const cancelItemEdit = document.querySelector("[data-cancel-item-edit]");
if (cancelItemEdit && editDialog) cancelItemEdit.addEventListener("click", () => editDialog.close());
if (editForm) {
  editForm.addEventListener("submit", async event => {
    event.preventDefault();
    try { await api(`/items/${editingId}`, { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload(editForm)) }); location.reload(); }
    catch (error) { document.querySelector("#item-edit-error").textContent = error.message; }
  });
}

document.querySelectorAll("[data-add-stock]").forEach(button => button.addEventListener("click", () => { stockItemId = button.dataset.addStock; stockDialog.showModal(); }));
const cancelStock = document.querySelector("[data-cancel-stock]");
if (cancelStock && stockDialog) cancelStock.addEventListener("click", () => stockDialog.close());
if (stockForm) {
  stockForm.addEventListener("submit", async event => {
    event.preventDefault();
    try { await api(`/items/adjust-stock/${stockItemId}`, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ quantity: Number(stockForm.elements.namedItem("quantity").value), reason: stockForm.elements.namedItem("reason").value }) }); location.reload(); }
    catch (error) { document.querySelector("#stock-error").textContent = error.message; }
  });
}

document.querySelectorAll("[data-view-item]").forEach(button => button.addEventListener("click", async () => {
  detailsError.textContent = "";
  ["movements", "sales", "purchases"].forEach(section => {
    document.querySelector(`#item-details-${section}`).innerHTML = emptyRow(section === "sales" ? 7 : section === "purchases" ? 5 : 4, "Loading...");
  });
  detailsDialog.showModal();
  try {
    const data = await api(`/items/${button.dataset.id}/details`);
    const item = data.item;
    document.querySelector('[data-detail="name"]').textContent = item.name;
    document.querySelector('[data-detail="barcode"]').textContent = item.barcode;
    document.querySelector('[data-detail="description"]').textContent = item.description || "-";
    document.querySelector('[data-detail="category"]').textContent = item.category;
    document.querySelector('[data-detail="stock"]').textContent = `${item.quantity} ${item.unit}`;
    document.querySelector('[data-detail="purchase_price"]').textContent = item.purchase_price;
    document.querySelector('[data-detail="selling_price_wholesale"]').textContent = item.selling_price_wholesale;
    document.querySelector('[data-detail="selling_price_retail"]').textContent = item.selling_price_retail;
    document.querySelector('[data-detail="wholesale_threshold"]').textContent = item.wholesale_threshold;

    document.querySelector("#item-details-movements").innerHTML = data.movements.length
      ? data.movements.map(row => `<tr><td>${escapeHtml(formatDate(row.created_at))}</td><td>${escapeHtml(row.movement_type)}</td><td>${escapeHtml(row.quantity)}</td><td>${escapeHtml(row.note)}</td></tr>`).join("")
      : emptyRow(4, "No stock history.");
    document.querySelector("#item-details-sales").innerHTML = data.sales.length
      ? data.sales.map(row => `<tr><td>${escapeHtml(formatDate(row.created_at))}</td><td>${escapeHtml(row.id)}</td><td>${escapeHtml(row.quantity)}</td><td>${escapeHtml(row.unit_price)}</td><td>${escapeHtml(row.discount_amount || 0)}</td><td>${escapeHtml(row.total_price)}</td><td>${escapeHtml(row.payment_method || "")}</td></tr>`).join("")
      : emptyRow(7, "No sales.");
    document.querySelector("#item-details-purchases").innerHTML = data.purchases.length
      ? data.purchases.map(row => `<tr><td>${escapeHtml(formatDate(row.created_at))}</td><td>${escapeHtml(row.purchase_id)}</td><td>${escapeHtml(row.quantity)}</td><td>${escapeHtml(row.unit_cost)}</td><td>${escapeHtml(row.total_amount)}</td></tr>`).join("")
      : emptyRow(5, "No purchases.");
  } catch (error) {
    detailsError.textContent = error.message;
    ["movements", "sales", "purchases"].forEach(section => {
      document.querySelector(`#item-details-${section}`).innerHTML = "";
    });
  }
}));
document.querySelector("[data-close-item-details]").addEventListener("click", () => detailsDialog.close());

document.querySelectorAll("[data-delete-item]").forEach(button => button.addEventListener("click", async () => {
  if (!confirm("Delete this item?")) return;
  try { await api(`/items/${button.dataset.deleteItem}`, { method: "DELETE" }); location.reload(); }
  catch (error) { alert(error.message); }
}));
