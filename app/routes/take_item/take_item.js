document.addEventListener("DOMContentLoaded", () => {
  let reader = null;
  let isScanning = false;
  let scannedItems = [];

  const saved = sessionStorage.getItem("scannedItems_take");
  if (saved) {
    try {
      scannedItems = JSON.parse(saved);
      console.log("🔄 Restored scannedItems from sessionStorage:", scannedItems);
      renderTable();
    } catch (err) {
      console.error("❌ Failed to parse scannedItems from sessionStorage", err);
    }
  }

  let allSuggestions = [];
  let showingAll = false;

  const INITIAL_SCAN_DELAY_MS = 3000;
  let scannerReadyTime = 0;

function startScanner() {
    const readerEl = document.getElementById("reader");
    const stopBtn = document.getElementById("stopBtn");

    if (!reader) reader = new Html5Qrcode("reader");

    // Show the scanner and stop button
    readerEl.classList.remove("d-none");
    stopBtn.classList.remove("d-none");

    // Scroll to center the scanner view
    setTimeout(() => {
    const readerRect = readerEl.getBoundingClientRect();
    const offset = 200; // Increase this until it scrolls enough
    const scrollPosition = window.pageYOffset + readerRect.top - (window.innerHeight / 2) + offset;

    window.scrollTo({
        top: scrollPosition,
        behavior: 'smooth'
    });
}, 50);

    if (!isScanning) {
        scannerReadyTime = Date.now() + INITIAL_SCAN_DELAY_MS;

        reader.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: 250 },
            async (decodedText) => {
                if (Date.now() < scannerReadyTime) return;

                isScanning = false;
                await reader.stop();
                await reader.clear();
                readerEl.classList.add("d-none");
                stopBtn.classList.add("d-none");
                await handleScan(decodedText);
            }
        )
        .then(() => {
            isScanning = true;
            console.log("📷 Scanner started — waiting for aim delay...");
        })
        .catch(err => console.error("Error starting scanner:", err));
    }
}

  function stopScanner() {
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
  }

  async function handleScan(qrData) {
    const res = await fetch("/api/get_item_by_qr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ qr_code: qrData })
    });

    const item = await res.json();
    if (!item || !item.product_name) {
      return Swal.fire({
        icon: "error",
        title: "Not found",
        text: "QR code did not match any article."
      });
    }

    const exists = scannedItems.find(i => i.article_number === item.article_number);
    if (!exists) {
      scannedItems.push({ ...item, quantity: 1 });
      renderTable();
    }
  }

  // ================== Suggestions ==================
  window.fetchSuggestions = async function () {
    const query = document.getElementById("manualSearch").value.trim();
    const cardArea = document.getElementById("suggestionCards");
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
      scannedItems.push({ ...item, quantity: 1 });
      renderTable();
    }
  };

  function renderTable() {
    const tbody = document.getElementById("scannedItemsBody");
    tbody.innerHTML = "";

    scannedItems.forEach((item, index) => {
      const imageUrl = item.product_image_url || '/static/placeholder.png';

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>
          <img src="${imageUrl}" class="scanned-img"
               onerror="this.src='/static/placeholder.png';" alt="Item image">
        </td>
        <td>${item.article_number}</td>
        <td>${item.product_name}</td>
        <td>${item.location || ''}</td>
        <td>${item.unit || ''}</td>
        <td>${item.category || 'Uncategorized'}</td>
        <td>${item.stock ?? ''}</td>
        <td>
         <input type="number" min="1" value="${item.quantity}"
                onchange="updateQuantity(${index}, this.value)"
                class="form-control form-control-sm" />
        </td>
        <td>
          <button class="btn btn-sm btn-danger" onclick="removeItem(${index})">Delete</button>
        </td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById("totalItems").innerText = scannedItems.length;
    document.getElementById("confirmBtn").classList.toggle("d-none", scannedItems.length === 0);
  }

  window.updateQuantity = updateQty;

  function updateQty(index, value) {
    console.log(`Updating index ${index} to value ${value}`);
    const numValue = parseInt(value);
    scannedItems[index].quantity = Math.max(1, numValue);
    console.log("Updated scannedItems:", scannedItems);
    sessionStorage.setItem("scannedItems_take", JSON.stringify(scannedItems));
    renderTable();
  }



  function removeItem(idx) {
    scannedItems.splice(idx, 1);
    sessionStorage.setItem("scannedItems_take", JSON.stringify(scannedItems));
    renderTable();
  }

  window.removeItem = removeItem;

function submitItems() {
  console.log("▶️ submitItems() called");
  console.log("Current scannedItems:", scannedItems);

  if (!scannedItems || scannedItems.length === 0) {
    return Swal.fire({
      icon: 'warning',
      title: 'No Items Selected',
      text: 'Please add at least one item.',
      background: '#000',
      color: '#fff',
      iconColor: '#4CAF50',
      confirmButtonColor: '#4CAF50'
    });
  }

  const projectNumber = document.getElementById("projectSearch")?.value.trim() || "";

  const itemSummary = scannedItems.map(i => ({
    article_number: i.article_number,
    product_name: i.product_name,
    quantity: parseInt(i.quantity) || 1,
    action: "take"
  }));

  const body = new URLSearchParams({
    summary: JSON.stringify(itemSummary),
    project_number: projectNumber
  });

  fetch("/api/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  })
    .then(res => {
      if (!res.ok) throw new Error("Confirm failed");

      if (projectNumber) {
        return fetch("/api/insert_project_items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_number: projectNumber,
            items: itemSummary
          })
        });
      }
    })
    .then(res => {
      if (res && !res.ok) throw new Error("Project insert failed");

      Swal.fire({
        icon: 'success',
        title: 'Items Taken',
        text: 'The article(s) have been taken successfully.',
        background: '#000',
        color: '#fff',
        iconColor: '#4CAF50',
        confirmButtonColor: '#4CAF50'
      }).then(() => {
        sessionStorage.removeItem("scannedItems_take");
        location.href = "/home";
      });
    })
    .catch(err => {
      console.error("❌ Error:", err);
      Swal.fire({
        icon: 'error',
        title: 'Error',
        text: err.message || 'Something went wrong.',
        background: '#000',
        color: '#fff',
        iconColor: '#4CAF50',
        confirmButtonColor: '#4CAF50'
      });
    });
}



   window.addItemForTake = function (item, qty) {
      const addQty = Math.max(1, parseInt(qty || 1, 10));
      const existing = scannedItems.find(i => i.id === item.id);
      if (existing) {
        existing.quantity = (parseInt(existing.quantity, 10) || 0) + addQty;
      } else {
        scannedItems.push({ ...item, quantity: addQty });
      }

      sessionStorage.setItem("scannedItems_take", JSON.stringify(scannedItems));
      Swal.fire({
        icon: 'success',
        title: 'Item Added',
        text: `${item.product_name} added (${addQty}).`,
        background: '#000',
        color: '#fff',
        iconColor: '#4CAF50',
        confirmButtonColor: '#4CAF50'
      }).then(() => {
        location.href = "/catalog";
      });
   };

  window.startScanner = startScanner;
  window.stopScanner = stopScanner;
  window.removeItem = removeItem;

  // ✅ DOM ready handler last
  console.log("✅ take_item.js loaded");

const confirmBtn = document.getElementById("confirmBtn");
if (confirmBtn) {
  confirmBtn.addEventListener("click", () => {
    confirmBtn.disabled = true;
    submitItems();
    setTimeout(() => {
      confirmBtn.disabled = false;
    }, 5000);
  });
}

window.fetchProjectItems = async function () {
  const projectNumber = document.getElementById("projectSearch").value.trim();
  const tableBody = document.getElementById("scannedItemsBody");
  const totalItems = document.getElementById("totalItems");

  if (!projectNumber) {
    return Swal.fire({
      icon: 'warning',
      title: 'Missing Input',
      text: 'Please enter a project number.',
      background: '#000',
      color: '#fff',
      iconColor: '#4CAF50',
      confirmButtonColor: '#4CAF50'
    });
  }

  const res = await fetch("/api/project_items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project_number: projectNumber })
  });

  const data = await res.json();
  tableBody.innerHTML = "";
  totalItems.textContent = "0";

  if (!res.ok) {
    return Swal.fire({
      icon: 'error',
      title: 'Error',
      text: data.error || 'Failed to load items.',
      background: '#000',
      color: '#fff',
      iconColor: '#4CAF50',
      confirmButtonColor: '#4CAF50'
    });
  }

  if (data.items.length === 0) {
    return Swal.fire({
      icon: 'info',
      title: 'No Items',
      text: 'This project has no items.',
      background: '#000',
      color: '#fff',
      iconColor: '#4CAF50',
      confirmButtonColor: '#4CAF50'
    });
  }

  scannedItems = data.items.map(item => ({
  article_number: item.item_id,
  product_name: item.item_name,
  quantity: item.quantity,
  location: item.location,
  unit: item.unit,
  category: item.type,
  stock: item.available,
  product_image_url: item.image_url
}));

sessionStorage.setItem("scannedItems_take", JSON.stringify(scannedItems));
renderTable();

}


});
