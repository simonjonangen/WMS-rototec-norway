document.addEventListener("DOMContentLoaded", function () {
  console.log("✅ create_project.js loaded");

  // Global variables
  let projectItems = [];
  let selectedWorkers = [];
  let allWorkers = [];
  let allItems = [];

  // Initialize the form
  initForm();

  // Fetch workers and items when page loads
  fetchWorkers();
  fetchAllItems();

  // Form submission handler
  const projectForm = document.getElementById("projectForm");
  if (projectForm) {
    projectForm.addEventListener("submit", function (e) {
      e.preventDefault();
      submitProject();
    });
  }

  // Worker search functionality
  // Worker search functionality
 const workerSearch = document.getElementById("workerSearch");
  if (workerSearch) {
   ["input", "change", "keyup", "search"].forEach(ev =>
     workerSearch.addEventListener(ev, filterWorkers)
   );
   // If the field is prefilled, reflect it immediately
   filterWorkers();
  }

  // Clear worker search
  const clearWorkerSearch = document.getElementById("clearWorkerSearch");
  if (clearWorkerSearch) {
    clearWorkerSearch.addEventListener("click", function() {
      workerSearch.value = "";
      filterWorkers();
    });
  }

  // Item search functionality
  const itemSearch = document.getElementById("itemSearch");
  if (itemSearch) {
    itemSearch.addEventListener("input", debounce(searchItems, 300));
  }

  // Add item button handler
  const addItemBtn = document.getElementById("addItem");
  if (addItemBtn) {
    addItemBtn.addEventListener("click", addSelectedItem);
  }

  // Initialize the form
  function initForm() {
    // Set default dates
    const today = new Date().toISOString().split('T')[0];
    document.getElementById("startDate").value = today;

    const nextWeek = new Date();
    nextWeek.setDate(nextWeek.getDate() + 7);
    document.getElementById("endDate").value = nextWeek.toISOString().split('T')[0];
  }

  // Fetch available workers
    async function fetchWorkers() {
       try {
          const res = await fetch("/api/get_workers");
          const workers = await res.json();
          allWorkers = workers;

         // Always apply current search term (even if the user started typing before fetch finished)
         if (typeof filterWorkers === "function") {
           filterWorkers();
         } else {
          renderWorkersList(allWorkers);
        }
       } catch (err) {
         console.error("Error fetching workers:", err);
         showError("Failed to load workers list");
       }
  }


  // Fetch all items from catalog
    async function fetchAllItems() {
        try {
          const res = await fetch("/api/search_items");
          allItems = await res.json();
         // Apply whatever is already typed in the box (handles typing before fetch completes)
         if (typeof searchItems === "function") {
           searchItems();
         }
        } catch (err) {
          console.error("Error fetching items:", err);
          showError("Failed to load items list");
        }
  }


  // Filter workers based on search input
  function filterWorkers() {
    const searchTerm = workerSearch.value.toLowerCase();
    const filtered = allWorkers.filter(worker =>
      (worker.name && worker.name.toLowerCase().includes(searchTerm)) ||
      (worker.username && worker.username.toLowerCase().includes(searchTerm))
    );
    renderWorkersList(filtered);
  }

  // Render workers list
  function renderWorkersList(workers) {
    const workersList = document.querySelector(".workers-list");
    workersList.innerHTML = "";

    workers.forEach(worker => {
      const isSelected = selectedWorkers.some(w => w.username === worker.username);
      const workerEl = document.createElement("div");
      workerEl.className = `worker-item p-2 mb-1 rounded ${isSelected ? "bg-success" : "bg-secondary"}`;
      workerEl.dataset.username = worker.username;
      workerEl.dataset.name = worker.name || worker.username;
      workerEl.textContent = `${worker.name || worker.username} (${worker.username})`;
      workerEl.onclick = function() { toggleWorkerSelection(this); };
      workersList.appendChild(workerEl);
    });
  }

  // Toggle worker selection
  window.toggleWorkerSelection = function(element) {
    const username = element.dataset.username;
    const name = element.dataset.name;
    const worker = { username, name };

    const index = selectedWorkers.findIndex(w => w.username === username);

    if (index === -1) {
      // Add worker if not already selected
      selectedWorkers.push(worker);
      element.classList.add("bg-success");
      element.classList.remove("bg-secondary");
    } else {
      // Remove worker if already selected
      selectedWorkers.splice(index, 1);
      element.classList.remove("bg-success");
      element.classList.add("bg-secondary");
    }

    renderSelectedWorkers();
  }

  // Render selected workers
  function renderSelectedWorkers() {
    const selectedList = document.getElementById("selectedWorkersList");
    selectedList.innerHTML = "";

    selectedWorkers.forEach(worker => {
      const badge = document.createElement("span");
      badge.className = "badge bg-success me-1 mb-1";
      badge.textContent = `${worker.name} (${worker.username})`;

      const removeBtn = document.createElement("button");
      removeBtn.className = "btn-close btn-close-white ms-1";
      removeBtn.style.fontSize = "0.5rem";
      removeBtn.onclick = function(e) {
        e.stopPropagation();
        removeSelectedWorker(worker.username);
      };

      badge.appendChild(removeBtn);
      selectedList.appendChild(badge);
    });
  }

  // Remove selected worker
  function removeSelectedWorker(username) {
    selectedWorkers = selectedWorkers.filter(w => w.username !== username);
    renderSelectedWorkers();

    // Update the workers list highlighting
    const workerItems = document.querySelectorAll(".worker-item");
    workerItems.forEach(item => {
      if (item.dataset.username === username) {
        item.classList.remove("bg-success");
        item.classList.add("bg-secondary");
      }
    });
  }

  // Search items in catalog
  async function searchItems() {
    const query = itemSearch.value.trim().toLowerCase();
    const resultsContainer = document.querySelector(".search-results");

    if (query.length < 1) {
      resultsContainer.classList.add("d-none");
      return;
    }

    const matchedItems = allItems.filter(item =>
      item.product_name && item.product_name.toLowerCase().includes(query)
    );

    if (matchedItems.length === 0) {
      resultsContainer.innerHTML = "<div class='p-2 text-white'>No items found</div>";
      resultsContainer.classList.remove("d-none");
      return;
    }

    resultsContainer.innerHTML = "";
    matchedItems.forEach(item => {
      const itemEl = document.createElement("div");
      itemEl.className = "item-result p-2 mb-1 rounded bg-secondary";
      itemEl.dataset.itemId = item.article_number;
      itemEl.dataset.itemName = item.product_name;
      itemEl.innerHTML = `
        <strong>${item.product_name}</strong>
        <small class="d-block">ID: ${item.article_number}</small>
        <small class="d-block">Location: ${item.location || 'N/A'}</small>
      `;
      itemEl.onclick = function() { selectItem(this); };
      resultsContainer.appendChild(itemEl);
    });

    resultsContainer.classList.remove("d-none");
  }

  // Select item from search results
  function selectItem(element) {
    itemSearch.value = element.dataset.itemName;
    document.querySelector(".search-results").classList.add("d-none");
  }

  // Add selected item to project list
  function addSelectedItem() {
    const itemName = itemSearch.value.trim();
    if (!itemName) {
      showError("Please select an item first");
      return;
    }

    const matchedItem = allItems.find(item =>
      item.product_name && item.product_name.toLowerCase() === itemName.toLowerCase()
    );

    if (!matchedItem) {
      showError("Item not found in catalog");
      return;
    }

    // Check if item already exists
    const exists = projectItems.find(item => item.item_id === matchedItem.article_number);
    if (exists) {
      exists.quantity += 1;
    } else {
      projectItems.push({
        item_id: matchedItem.article_number,
        item_name: matchedItem.product_name,
        quantity: 1
      });
    }

    // Clear search
    itemSearch.value = "";
    document.querySelector(".search-results").classList.add("d-none");

    renderItemsTable();
  }

  // Debounce function for search
  function debounce(func, timeout = 300) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => { func.apply(this, args); }, timeout);
    };
  }

  // Render items table
  function renderItemsTable() {
    const tbody = document.querySelector("#itemsTable tbody");
    tbody.innerHTML = "";

    projectItems.forEach((item, index) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${item.item_id}</td>
        <td>${item.item_name}</td>
        <td>
          <input type="number" min="1" value="${item.quantity}"
                 onchange="updateItemQuantity(${index}, this.value)"
                 style="width: 60px;">
        </td>
        <td>
          <button class="btn btn-sm btn-danger" onclick="removeItem(${index})">Remove</button>
        </td>
      `;
      tbody.appendChild(row);
    });
  }

  // Update item quantity
  window.updateItemQuantity = function(index, value) {
    const quantity = parseInt(value);
    if (!isNaN(quantity) && quantity > 0) {
      projectItems[index].quantity = quantity;
      renderItemsTable();
    }
  };

  // Remove item from list
  window.removeItem = function(index) {
    projectItems.splice(index, 1);
    renderItemsTable();
  };

// Submit project form
async function submitProject() {
  console.log("🚀 submitProject() called");
  const submitBtn = document.querySelector('[type="submit"]');
  const originalBtnHTML = submitBtn.innerHTML;

  try {
    // Disable button but don't show spinner
    submitBtn.disabled = true;

    const projectData = {
      project_number: document.getElementById("projectNumber").value.trim(),
      customer_name: document.getElementById("customerName").value.trim(),
      workers: selectedWorkers,
      start_date: document.getElementById("startDate").value,
      end_date: document.getElementById("endDate").value,
      items: projectItems
    };

    // Validation checks
    if (!projectData.project_number) {
      throw new Error("Project number is required");
    }
    if (projectData.workers.length === 0) {
      throw new Error("Please select at least one worker");
    }
    if (!projectData.start_date || !projectData.end_date) {
      throw new Error("Please select both start and end dates");
    }
    if (projectData.items.length === 0) {
      throw new Error("Please add at least one item to the project");
    }

    const response = await fetch("/api/create_project", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify(projectData)
    });

    const result = await response.json();

    if (!response.ok || !result.success) {
      throw new Error(result.message || "Failed to create project");
    }

    // Show success notification
    await Swal.fire({
      icon: "success",
      title: "Success!",
      text: result.message,
      background: "#000",
      color: "#fff",
      iconColor: "#4CAF50",
      confirmButtonColor: "#4CAF50",
      customClass: {
        popup: "swal-font"
      }
    });

    // Redirect after success
    window.location.href = "/home";

  } catch (error) {
    console.error("❌ Project creation error:", error);
    await Swal.fire({
      icon: "error",
      title: "Error",
      text: error.message,
      background: "#000",
      color: "#fff",
      iconColor: "#4CAF50",
      confirmButtonColor: "#4CAF50",
      customClass: {
        popup: "swal-font"
      }
    });
  } finally {
    // Re-enable button without changing content
    submitBtn.disabled = false;
  }
}
});