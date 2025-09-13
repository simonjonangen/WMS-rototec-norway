document.addEventListener("DOMContentLoaded", () => {
  console.log("✅ add_stock.js loaded");

  let reader = null;
  let isScanning = false;
  let lastScanTime = 0;
  let scannerReadyTime = 0;
  const INITIAL_SCAN_DELAY_MS = 3000;

  let scannedItems = [];
  let allSuggestions = [];
  let showingAll = false;

  const saved = sessionStorage.getItem("scannedItems_add");
  if (saved) {
    try {
      scannedItems = JSON.parse(saved);
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

    // Show the scanner and stop button
    readerEl.classList.remove("d-none");
    stopBtn.classList.remove("d-none");

    // Scroll to center the scanner with an offset (adjust the 200 value as needed)
    setTimeout(() => {
        const readerRect = readerEl.getBoundingClientRect();
        const offset = 200; // Increase this number if you need to scroll further down
        const scrollPosition = window.pageYOffset + readerRect.top - (window.innerHeight / 2) + offset;

        window.scrollTo({
            top: scrollPosition,
            behavior: 'smooth'
        });
    }, 50); // Small delay to ensure element is visible before scrolling

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
    if (scannedItems.find(i => i.id === item.id)) return alert("Already added.");

    item.quantity = 1;
    scannedItems.push(item);
    renderTable();
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

  // ================== Render Table ==================
  function renderTable() {
    const tbody = document.getElementById("scannedItemsBody");
    const confirmBtn = document.getElementById("confirmBtn");
    tbody.innerHTML = "";
    let total = 0;

    scannedItems.forEach((item, idx) => {
      total += item.quantity;
      tbody.innerHTML += `
        <tr style="font-size: 0.85rem;">
          <td style="width: 60px;">
            <img src="${item.product_image_url || '/static/placeholder.png'}" class="img-fluid" style="max-height: 50px;" onerror="this.src='/static/placeholder.png'">
          </td>
          <td style="width: 100px;">${item.article_number}</td>
          <td style="width: 120px;">${item.product_name}</td>
          <td style="width: 100px;">${item.location || ""}</td>
          <td style="width: 80px;">${item.unit || ""}</td>
          <td style="width: 100px;">${item.category || ""}</td>
          <td style="width: 90px;">${item.stock ?? ""}</td>
          <td style="width: 80px;">
            <input type="number" min="1" value="${item.quantity}" onchange="updateQuantity(${idx}, this.value)" style="width: 60px;">
          </td>
          <td><button class="btn btn-sm btn-danger" onclick="removeItem(${idx})">Remove</button></td>
        </tr>`;
    });

    document.getElementById("totalItems").textContent = total;
    confirmBtn.classList.toggle("d-none", scannedItems.length === 0);
  }

  window.updateQuantity = function (idx, val) {
    scannedItems[idx].quantity = Math.max(1, parseInt(val));
    renderTable();
  };

  window.removeItem = function (idx) {
    scannedItems.splice(idx, 1);
    sessionStorage.setItem("scannedItems_add", JSON.stringify(scannedItems));
    renderTable();
  };


  // ================== Submit Return ==================
  window.submitItems = function () {
  console.log("▶️ submitItems() called");

  if (!scannedItems || scannedItems.length === 0) {
    Swal.fire({
      icon: "warning",
      title: "No Items Selected",
      text: "Please add at least one item before submitting an add.",
      background: "#000",
      color: "#fff",
      iconColor: "#4CAF50",
      confirmButtonColor: "#4CAF50"
    });
    return;
  }

  const body = new URLSearchParams({
    summary: JSON.stringify(scannedItems.map(i => ({
      article_number: i.article_number,
      quantity: i.quantity,
      action: "return"
    })))
  });

  fetch("/api/confirm", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  })
    .then(res => {
      if (res.ok) {
        Swal.fire({
          icon: "success",
          title: "Add Confirmed",
          text: "The article has been added successfully.",
          background: "#000",
          color: "#fff",
          iconColor: "#4CAF50",
          confirmButtonColor: "#4CAF50"
        }).then(() => {
          sessionStorage.removeItem("scannedItems_add");
          location.href = "/home";
        });
      } else {
        Swal.fire({
          icon: "error",
          title: "Error",
          text: "Something went wrong.",
          background: "#000",
          color: "#fff",
          iconColor: "#4CAF50",
          confirmButtonColor: "#4CAF50"
        });
      }
    })
    .catch(err => {
      console.error("❌ Network error:", err);
      Swal.fire({
        icon: "error",
        title: "Network Error",
        text: "Check your connection.",
        background: "#000",
        color: "#fff",
        iconColor: "#4CAF50",
        confirmButtonColor: "#4CAF50"
      });
    });
};

window.addItemForReturn = function(item, qty) {
  const addQty = Math.max(1, parseInt(qty || 1, 10));
  const existing = scannedItems.find(i => i.id === item.id);
  if (existing) {
    existing.quantity = (parseInt(existing.quantity, 10) || 0) + addQty;
  } else {
    scannedItems.push({ ...item, quantity: addQty });
  }

  sessionStorage.setItem("scannedItems_add", JSON.stringify(scannedItems));

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
      setTimeout(() => {
        confirmBtn.disabled = false;
      }, 5000);
    });
  }
});


