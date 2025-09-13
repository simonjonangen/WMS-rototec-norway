let reader = null;
let isScanning = false;
let selectedItem = null;

let lastScanTime = 0;
let scannerReadyTime = 0;
const INITIAL_SCAN_DELAY_MS = 3000; // 1.5 second delay before first valid scan

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
    reader.stop().then(() => {
      reader.clear();
      document.getElementById("reader").classList.add("d-none");
      document.getElementById("stopBtn").classList.add("d-none");
      isScanning = false;
    }).catch(err => {
      console.error("Error stopping QR scanner:", err);
    });
  }
}

async function fetchItem(qrData) {
  const res = await fetch("/api/get_item_by_qr", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ qr_code: qrData })
  });

  const item = await res.json();
  // ✅ CORRECT — use product_name instead
  if (!item || !item.product_name) {
    Swal.fire({
      icon: 'error',
      title: 'Article not found',
      text: 'QR-code did not match any article.'
    });
    return;
  }

  selectedItem = item;
  renderItem();
}

let allSuggestions = [];
let showingAll = false;

async function fetchSuggestions() {
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
}

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

function toggleCardLimit() {
  showingAll = !showingAll;
  renderLimitedSuggestions();
}

function selectItem(item) {
  selectedItem = { ...item, quantity: 1 };
  renderItem();
}


function renderItem() {
  const tbody = document.getElementById("selectedItemBody");
  if (!selectedItem) return;

  const imageUrl = selectedItem.product_image_url || '/static/placeholder.png';

  tbody.innerHTML = `
    <tr style="font-size: 0.85rem;">
      <td style="width: 60px;">
        <img src="${imageUrl}"
             class="img-fluid" style="max-height: 50px;"
             onerror="this.src='/static/placeholder.png'">
      </td>
      <td style="width: 100px;">${selectedItem.article_number}</td>
      <td style="width: 120px;">${selectedItem.product_name}</td>
      <td style="width: 100px;">${selectedItem.location || ""}</td>
      <td style="width: 80px;">${selectedItem.unit || ""}</td>
      <td style="width: 100px;">${selectedItem.category || ""}</td>
      <td style="width: 90px;">${selectedItem.stock ?? ""}</td>
      <td><button class="btn btn-sm btn-danger" onclick="removeSelectedItem()">Remove</button></td>
    </tr>`;
}



function removeSelectedItem() {
  selectedItem = null;
  document.getElementById("selectedItemBody").innerHTML = "";
}


function submitReport() {
  console.log("🚀 submitReport() called");
  if (!selectedItem) {
    Swal.fire({
  icon: 'warning',
  title: 'Choose Article',
  text: 'Please choose an article in order to proceed.',
  background: '#000',
  color: '#fff',
  iconColor: '#4CAF50',
  confirmButtonColor: '#4CAF50',
  customClass: {
    popup: 'swal-font'
  }
});

    return;
  }

  const issueTypes = Array.from(document.querySelectorAll("input[name='issue_type']:checked")).map(i => i.value);
  if (issueTypes.length === 0) {
    Swal.fire({
      icon: 'warning',
      title: 'Issue Type',
      text: 'Issue type not selected, please select issue type.',
      background: '#000',
      color: '#fff',
      iconColor: '#4CAF50',
      confirmButtonColor: '#4CAF50',
      customClass: {
        popup: 'swal-font'
      }
    });

    return;
  }

  const otherText = document.getElementById("otherText").value.trim();
  const hasOther = issueTypes.includes("other");

  if (hasOther && otherText) {
    const index = issueTypes.indexOf("other");
    issueTypes[index] = `other: ${otherText}`;
  }

  const formData = new FormData();
  formData.append("article_number", selectedItem.article_number);
  formData.append("issues", JSON.stringify(issueTypes));
  formData.append("comment", otherText);
  const count = document.getElementById("count")?.value || "1";
  formData.append("count", count);


  const photo = document.getElementById("photo").files[0];
  if (photo) {
    formData.append("photo", photo);
  }

  fetch("/report", {
    method: "POST",
    body: formData
  }).then(res => {
    if (res.ok) {
      Swal.fire({
          icon: 'success',
          title: 'Report sent',
          text: 'Your issue report has been submitted.',
          background: '#000',
          color: '#fff',
          iconColor: '#4CAF50',
          confirmButtonColor: '#4CAF50',
          customClass: {
            popup: 'swal-font'
          }
        }).then(() => {
          location.href = "/home";
        });

    } else {
      Swal.fire({
  icon: 'error',
  title: 'Error',
  text: 'Something went wrong when sending the issue report.',
  background: '#000',
  color: '#fff',
  iconColor: '#4CAF50',
  confirmButtonColor: '#4CAF50',
  customClass: {
    popup: 'swal-font'
  }
});

    }
  }).catch(err => {
    console.error("❌ Network error:", err);
    Swal.fire({
      icon: 'error',
      title: 'Network Error',
      text: 'Please check your network connection.',
      background: '#000',
      color: '#fff',
      iconColor: '#4CAF50',
      confirmButtonColor: '#4CAF50',
      customClass: {
        popup: 'swal-font'
      }
    });

  });
}

async function handleScan(qrData) {
  console.log("📦 QR code scanned:", qrData);

  const res = await fetch("/api/get_item_by_qr", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qr_code: qrData })
  });

  const item = await res.json();

  // ✅ CORRECT — use product_name instead
   if (!item || !item.product_name) {
    Swal.fire({
  icon: 'error',
  title: 'Item Error',
  text: 'Item not found in catalog, please try again.',
  background: '#000',
  color: '#fff',
  iconColor: '#4CAF50',
  confirmButtonColor: '#4CAF50',
  customClass: {
    popup: 'swal-font'
  }
});

    return;
  }

  selectedItem = item;
  renderItem(); // shows the card in HTML
}
