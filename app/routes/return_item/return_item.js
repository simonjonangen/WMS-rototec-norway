document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ return_item.js loaded");

  let reader = null;
  let isScanning = false;
  let lastScanTime = 0;
  let scannerReadyTime = 0;
  const INITIAL_SCAN_DELAY_MS = 3000;

  let scannedItems = [];
  let allSuggestions = [];
  let showingAll = false;

  const RETURN_TYPES = ["returned", "broken", "used"]; // returned -> adds to stock

  // Restore previous session
  const saved = sessionStorage.getItem("scannedItems_return");
  if (saved) {
    try {
      scannedItems = JSON.parse(saved);
      // Backward compatibility: ensure each has return_type
      scannedItems.forEach(i => { if (!i.return_type) i.return_type = "returned"; });
      console.log("🔄 Restored scannedItems from sessionStorage:", scannedItems);
      renderTable();
    } catch (err) {
      console.error("❌ Failed to parse scannedItems from sessionStorage", err);
    }
  }

  // ================== Scanner ==================
  window.startScanner = function () {
    const readerEl = document.getElementById("reader");
    const stopBtn = document.getElementById("stopBtn");

    if (!reader) reader = new Html5Qrcode("reader");

    readerEl.classList.remove("d-none");
    stopBtn.classList.remove("d-none");

    setTimeout(() => {
      const readerRect = readerEl.getBoundingClientRect();
      const offset = 200;
      const scrollPosition = window.pageYOffset + readerRect.top - (window.innerHeight / 2) + offset;
      window.scrollTo({ top: scrollPosition, behavior: 'smooth' });
    }, 50);

    if (!isScanning) {
      scannerReadyTime = Date.now() + INITIAL_SCAN_DELAY_MS;

      reader.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: 250 },
        async (decodedText) => {
          const now = Date.now();
          if (now < scannerReadyTime) return;

          isScanning = false;
          await reader.stop();
          await reader.clear();
          readerEl.classList.add("d-none");
          stopBtn.classList.add("d-none");
          await handleScan(decodedText);
        },
        () => {}
      )
      .then(() => {
        isScanning = true;
        console.log("📷 Scanner started — waiting for aim delay...");
      })
      .catch(err => console.error("Error starting scanner:", err));
    }
  };

  window.stopScanner = function () {
    if (reader && isScanning) {
      reader.stop()
        .then(() => {
          reader.clear();
          document.getElementById("reader").classList.add("d-none");
          document.getElementById("stopBtn").classList.add("d-none");
          isScanning = false;
        })
        .catch(err => console.error("Error stopping scanner:", err));
    }
  };

  async function handleScan(qrData) {
    const res = await fetch("/api/get_item_by_qr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qr_code: qrData })
    });

    const item = await res.json();
    if (!item || !item.product_name) return alert("Item not found.");
    if (scannedItems.find(i => i.id === item.id || i.article_number === item.article_number)) {
      return alert("Already added.");
    }

    item.quantity = 1;
    item.return_type = "returned"; // default
    scannedItems.push(item);
    persistAndRender();
  }

  // ================== Suggestions (manual search) ==================
  window.fetchSuggestions = async function () {
    const query = document.getElementById("manualSearch")?.value?.trim();
    const cardArea = document.getElementById("suggestionCards");
    if (!cardArea) return;

    cardArea.innerHTML = "";
    allSuggestions = [];
    showingAll = false;

    if (!query) return;

    const res = await fetch(`/api/search_item?q=${encodeURIComponent(query)}`);
    const items = await res.json();
    if (!items.length) {
      cardArea.innerHTML = '<div class="alert alert-warning">No matches found</div>';
      return;
    }

    allSuggestions = items;
    renderLimitedSuggestions();
  };

  function renderLimitedSuggestions() {
    const cardArea = document.getElementById("suggestionCards");
    if (!cardArea) return;
    cardArea.innerHTML = "";
    const itemsToShow = showingAll ? allSuggestions : allSuggestions.slice(0, 3);

    itemsToShow.forEach(item => {
      const cardCol = document.createElement("div");
      cardCol.className = "col-md-4 d-flex justify-content-center mb-3";
      const imageUrl = item.product_image_url || `/static/product_images/${item.article_number}.png`;

      cardCol.innerHTML = `
        <div class="card shadow-sm" style="width: 100%; max-width: 260px; font-size: 0.8rem;">
          <div class="card-body d-flex flex-column justify-content-between p-2">
            <div>
              <h6 class="card-title mb-1" style="font-size: 0.85rem;">
                <a href="#" onclick='showItemDetails("${item.id || ""}")' style="text-decoration: none;">
                  ${item.product_name}
                </a>
              </h6>
              <p class="card-text text-muted mb-2" style="font-size: 0.75rem;">
                <strong>Location:</strong> ${item.location || "-"}<br>
                <strong>Category:</strong> ${item.category || "-"}<br>
                <strong>Stock:</strong> ${item.stock ?? "-"}
              </p>
            </div>
            <button class="btn btn-sm btn-success mt-auto" onclick='selectItem(${JSON.stringify(item)})'>Add</button>
          </div>
        </div>
      `;
      cardArea.appendChild(cardCol);
    });

    const loadMoreBtn = document.getElementById("loadMoreBtn");
    if (loadMoreBtn) {
      loadMoreBtn.classList.toggle("d-none", allSuggestions.length <= 3);
      loadMoreBtn.textContent = showingAll ? "Show less" : "Show more";
    }
  }

  window.toggleCardLimit = function () {
    showingAll = !showingAll;
    renderLimitedSuggestions();
  };

  window.selectItem = function (item) {
    const exists = scannedItems.find(i => i.article_number === item.article_number);
    if (!exists) {
      scannedItems.push({ ...item, quantity: 1, return_type: "returned" });
      persistAndRender();
    }
  };

  // ================== Project Items (parity with Take Item) ==================
  window.fetchProjectItems = async function () {
    const projectNumberInput = document.getElementById("projectSearch");
    const projectNumber = projectNumberInput ? projectNumberInput.value.trim() : "";
    const tableBody = document.getElementById("scannedItemsBody");
    const totalItems = document.getElementById("totalItems");

    if (!projectNumber) {
      return Swal.fire({
        icon: 'warning',
        title: 'Missing Input',
        text: 'Please enter a project number.'
      });
    }

    const res = await fetch("/api/project_returns", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project_number: projectNumber })
    });

    const data = await res.json();
    if (!res.ok) {
      if (tableBody) tableBody.innerHTML = "";
      if (totalItems) totalItems.textContent = "0";
      return Swal.fire({
        icon: 'error',
        title: 'Error',
        text: data.error || 'Failed to load items.'
      });
    }

    if (!data.items || data.items.length === 0) {
      if (tableBody) tableBody.innerHTML = "";
      if (totalItems) totalItems.textContent = "0";
      return Swal.fire({
        icon: 'info',
        title: 'No Items',
        text: 'This project has no items.'
      });
    }

    // Map to our structure; default return_type for each
    scannedItems = data.items.map(item => ({
      article_number: item.item_id,
      product_name: item.item_name,
      quantity: item.quantity || 1,
      location: item.location,
      unit: item.unit,
      category: item.type,
      stock: item.available,
      product_image_url: item.image_url,
      return_type: "returned"
    }));

    persistAndRender();
  };

  // ================== Render Table (adds Return Type column) ==================
  function ensureReturnTypeHeader() {
    // Try to insert a <th> "Return Type" before Quantity column in the first <thead> row
    const thead = document.querySelector("table thead tr");
    if (!thead) return;

    const existing = Array.from(thead.children).some(th =>
      th.textContent.trim().toLowerCase() === "return type"
    );
    if (existing) return;

    // Heuristic: insert before the last two headers (Quantity / Delete) if present
    const th = document.createElement("th");
    th.textContent = "Return Type";

    // Find "Quantity" header
    let qtyTh = Array.from(thead.children).find(th =>
      th.textContent.trim().toLowerCase().includes("quantity")
    );

    if (qtyTh && qtyTh.parentNode) {
      qtyTh.parentNode.insertBefore(th, qtyTh);
    } else {
      thead.appendChild(th);
    }
  }

  function renderTable() {
    ensureReturnTypeHeader();

    const tbody = document.getElementById("scannedItemsBody");
    const confirmBtn = document.getElementById("confirmBtn");
    if (!tbody) return;

    tbody.innerHTML = "";
    let total = 0;

    scannedItems.forEach((item, idx) => {
      total += (parseInt(item.quantity, 10) || 1);

      const image = item.product_image_url || '/static/placeholder.png';
      const options = RETURN_TYPES.map(rt =>
        `<option value="${rt}" ${rt === (item.return_type || "returned") ? "selected" : ""}>${rt}</option>`
      ).join("");

      tbody.innerHTML += `
        <tr style="font-size: 0.85rem;">
          <td style="width: 60px;">
            <img src="${image}" class="img-fluid" style="max-height: 50px;" onerror="this.src='/static/placeholder.png'">
          </td>
          <td style="width: 100px;">${item.article_number}</td>
          <td style="width: 120px;">${item.product_name}</td>
          <td style="width: 100px;">${item.location || ""}</td>
          <td style="width: 80px;">${item.unit || ""}</td>
          <td style="width: 100px;">${item.category || ""}</td>
          <td style="width: 90px;">${item.stock ?? ""}</td>

          <!-- NEW: Return Type select -->
          <td style="width: 120px;">
            <select class="form-select form-select-sm" onchange="updateReturnType(${idx}, this.value)">
              ${options}
            </select>
          </td>

          <td style="width: 80px;">
            <input type="number" min="1" value="${item.quantity}" onchange="updateQuantity(${idx}, this.value)" style="width: 60px;">
          </td>
          <td><button class="btn btn-sm btn-danger" onclick="removeItem(${idx})">Remove</button></td>
        </tr>`;
    });

    const totalEl = document.getElementById("totalItems");
    if (totalEl) totalEl.textContent = total;

    if (confirmBtn) confirmBtn.classList.toggle("d-none", scannedItems.length === 0);
  }

  window.updateReturnType = function (idx, val) {
    scannedItems[idx].return_type = (val || "returned");
    persist();
  };

  window.updateQuantity = function (idx, val) {
    scannedItems[idx].quantity = Math.max(1, parseInt(val));
    persistAndRender();
  };

  window.removeItem = function (idx) {
    scannedItems.splice(idx, 1);
    persistAndRender();
  };

  function persist() {
    sessionStorage.setItem("scannedItems_return", JSON.stringify(scannedItems));
  }
  function persistAndRender() {
    persist();
    renderTable();
  }

// Replace the existing window.submitItems with this version
window.submitItems = function () {
  console.log("▶️ submitItems() called");

  if (!scannedItems || scannedItems.length === 0) {
    Swal.fire({
      icon: "warning",
      title: "No Items Selected",
      text: "Please add at least one item before submitting a return.",
      background: "#000",
      color: "#fff",
      iconColor: "#4CAF50",
      confirmButtonColor: "#4CAF50"
    });
    return;
  }

  // NEW: read project number (same input used elsewhere)
  const projectNumber = document.getElementById("projectSearch")?.value.trim() || "";

  const summary = scannedItems.map(i => {
    const rt = (i.return_type || "returned").toLowerCase();
    return {
      article_number: i.article_number,
      product_name: i.product_name,
      quantity: parseInt(i.quantity, 10) || 1,
      action: "return",                 // backend expects "return"
      return_type: rt,                  // for logging/reporting
      apply_to_stock: rt === "returned" // only returned adds back to stock
    };
  });

  const body = new URLSearchParams({
    summary: JSON.stringify(summary)
  });

  fetch("/api/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  })
  .then(res => {
    if (!res.ok) throw new Error("Confirm failed");

    // NEW: if a project number is present, mirror TakeItem by inserting into project items
    if (projectNumber) {
      return fetch("/api/insert_project_returns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_number: projectNumber,
          items: summary // includes action:return + return_type
        })
      });
    }
  })
  .then(res => {
    if (res && !res.ok) throw new Error("Project insert failed");

    Swal.fire({
      icon: "success",
      title: "Return Confirmed",
      text: "The article(s) have been submitted.",
      background: "#000",
      color: "#fff",
      iconColor: "#4CAF50",
      confirmButtonColor: "#4CAF50"
    }).then(() => {
      sessionStorage.removeItem("scannedItems_return");
      location.href = "/home";
    });
  })
  .catch(err => {
    console.error("❌ Error:", err);
    Swal.fire({
      icon: "error",
      title: "Error",
      text: err.message || "Something went wrong.",
      background: "#000",
      color: "#fff",
      iconColor: "#4CAF50",
      confirmButtonColor: "#4CAF50"
    });
  });
};


window.addItemForReturn = function(item, qty) {
  const addQty = Math.max(1, parseInt(qty || 1, 10));
  const existing = scannedItems.find(i => (i.id && i.id === item.id) || i.article_number === item.article_number);
  if (existing) {
    existing.quantity = (parseInt(existing.quantity, 10) || 0) + addQty;
  } else {
    scannedItems.push({ ...item, quantity: addQty, return_type: "returned" });
  }

  persist();

  Swal.fire({
    icon: 'success',
    title: 'Item Added',
    text: `${item.product_name} added to return (${addQty}).`,
    background: '#000',
    color: '#fff',
    iconColor: '#4CAF50',
    confirmButtonColor: '#4CAF50'
  }).then(() => {
    location.href = "/catalog";
  });
};

// ================== Button Bind ==================
const confirmBtn = document.getElementById("confirmBtn");
if (confirmBtn) {
  confirmBtn.addEventListener("click", () => {
    confirmBtn.disabled = true;
    submitItems();
    setTimeout(() => { confirmBtn.disabled = false; }, 5000);
  });
}
});

