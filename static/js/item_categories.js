async function submitJson(form, url) {
  const data = Object.fromEntries(new FormData(form));
  if (data.target_id) data.target_id = Number(data.target_id);
  if (data.percentage) data.percentage = Number(data.percentage);
  const response = await fetch(url, { method: "POST", credentials: "same-origin", headers: {"Content-Type":"application/json"}, body: JSON.stringify(data) });
  if (!response.ok) { const body = await response.json(); throw new Error(body.detail || "Request failed"); }
}
const categoryForm = document.querySelector("#category-form");
categoryForm.addEventListener("submit", async event => { event.preventDefault(); try { await submitJson(categoryForm, "/items/categories"); location.reload(); } catch (error) { document.querySelector("#category-error").textContent = error.message; } });
const discountForm = document.querySelector("#discount-form");
discountForm.addEventListener("submit", async event => { event.preventDefault(); try { await submitJson(discountForm, "/items/discounts"); location.reload(); } catch (error) { document.querySelector("#discount-error").textContent = error.message; } });
