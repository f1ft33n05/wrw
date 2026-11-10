(() => {
  const PAGE_SIZES = [10, 20, 50, 100, 200];

  function paginateTable(table) {
    if (table.dataset.paginationInitialized || table.hasAttribute("data-no-pagination")) return;

    const tbody = table.tBodies[0];
    if (
      !tbody
      || !tbody.rows.length
      || (tbody.rows.length === 1 && tbody.rows[0].hasAttribute("data-sales-empty"))
    ) return;

    table.dataset.paginationInitialized = "true";
    table.classList.add("paginated-table");

    const container = document.createElement("div");
    container.className = "table-pagination";
    container.innerHTML = `
      <label>Show
        <select aria-label="Rows per page">
          ${PAGE_SIZES.map((size) => `<option value="${size}">${size}</option>`).join("")}
        </select> entries
      </label>
      <p class="table-pagination-summary"></p>
      <div class="table-pagination-controls">
        <button type="button" data-table-page="previous">Prev</button>
        <button type="button" data-table-page="next">Next</button>
      </div>`;
    (table.closest(".table-scroll-container") || table).insertAdjacentElement("afterend", container);

    const select = container.querySelector("select");
    const summary = container.querySelector(".table-pagination-summary");
    const previous = container.querySelector('[data-table-page="previous"]');
    const next = container.querySelector('[data-table-page="next"]');
    const rows = Array.from(tbody.rows).filter((row) => !row.hasAttribute("data-sales-empty"));
    let currentPage = 1;

    function render() {
      const pageSize = Number(select.value);
      const matchingRows = rows.filter((row) => row.dataset.filterMatch !== "false");
      const matchingRowSet = new Set(matchingRows);
      const pageCount = Math.max(1, Math.ceil(matchingRows.length / pageSize));
      currentPage = Math.min(currentPage, pageCount);

      const start = (currentPage - 1) * pageSize;
      const end = Math.min(start + pageSize, matchingRows.length);
      let matchIndex = 0;
      rows.forEach((row, index) => {
        if (!matchingRowSet.has(row)) {
          row.hidden = true;
          return;
        }
        row.hidden = matchIndex < start || matchIndex >= end;
        matchIndex += 1;
      });

      summary.textContent = `${matchingRows.length ? start + 1 : 0}-${end} of ${matchingRows.length}`;
      previous.disabled = currentPage === 1;
      next.disabled = currentPage === pageCount;
      previous.setAttribute("aria-label", `Previous page, current page ${currentPage}`);
      next.setAttribute("aria-label", `Next page, current page ${currentPage}`);
      table.dispatchEvent(new Event("tablepagerender"));
    }

    select.addEventListener("change", () => {
      currentPage = 1;
      render();
    });
    previous.addEventListener("click", () => {
      currentPage -= 1;
      render();
    });
    next.addEventListener("click", () => {
      currentPage += 1;
      render();
    });
    table.addEventListener("tablefilterchange", () => {
      currentPage = 1;
      render();
    });
    render();
  }

  function paginateTables(root = document) {
    root.querySelectorAll("table:not([data-no-pagination])").forEach(paginateTable);
  }

  function wrapTables(root = document) {
    root.querySelectorAll("table:not([data-no-table-scroll])").forEach((table) => {
      if (table.closest(".table-scroll-container")) return;
      const wrapper = document.createElement("div");
      wrapper.className = "table-scroll-container";
      table.before(wrapper);
      wrapper.append(table);
    });
  }

  wrapTables();
  document.addEventListener("DOMContentLoaded", () => {
    wrapTables();
    paginateTables();
  });

  new MutationObserver(() => {
    wrapTables();
    paginateTables();
  }).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
