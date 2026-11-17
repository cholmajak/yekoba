/**
 * GreenHarvest Farm Management System (FMS) - JavaScript Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile Sidebar Toggle
  const mobileToggle = document.getElementById('mobileToggle');
  const sidebar = document.getElementById('sidebar');

  if (mobileToggle && sidebar) {
    mobileToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      sidebar.classList.toggle('open');
    });

    document.addEventListener('click', (e) => {
      if (!sidebar.contains(e.target) && !mobileToggle.contains(e.target)) {
        sidebar.classList.remove('open');
      }
    });
  }

  // 2. Alert Dismissal
  document.querySelectorAll('.alert-close').forEach(btn => {
    btn.addEventListener('click', () => {
      const alert = btn.closest('.alert');
      if (alert) {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-10px)';
        alert.style.transition = 'all 0.3s ease';
        setTimeout(() => alert.remove(), 300);
      }
    });
  });

  // 3. Generic Modal Handlers
  document.querySelectorAll('[data-modal-target]').forEach(trigger => {
    trigger.addEventListener('click', () => {
      const targetId = trigger.getAttribute('data-modal-target');
      const modal = document.getElementById(targetId);
      if (modal) {
        modal.classList.add('active');
      }
    });
  });

  document.querySelectorAll('[data-modal-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-backdrop');
      if (modal) {
        modal.classList.remove('active');
      }
    });
  });

  // Close modal when clicking outside backdrop
  document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        backdrop.classList.remove('active');
      }
    });
  });

  // 4. Delete Confirmation Helper
  window.confirmDelete = function(actionUrl, itemName = 'this item') {
    const confirmModal = document.getElementById('confirmDeleteModal');
    const deleteForm = document.getElementById('deleteConfirmForm');
    const deleteItemName = document.getElementById('deleteItemName');

    if (confirmModal && deleteForm) {
      deleteForm.action = actionUrl;
      if (deleteItemName) {
        deleteItemName.textContent = itemName;
      }
      confirmModal.classList.add('active');
    } else {
      if (confirm(`Are you sure you want to delete ${itemName}? This action cannot be undone.`)) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = actionUrl;
        document.body.appendChild(form);
        form.submit();
      }
    }
  };

  // 5. Client-Side Instant Table Filter
  const tableSearchInput = document.getElementById('clientTableSearch');
  if (tableSearchInput) {
    tableSearchInput.addEventListener('input', (e) => {
      const filter = e.target.value.toLowerCase();
      const rows = document.querySelectorAll('.data-table tbody tr');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(filter) ? '' : 'none';
      });
    });
  }

  // 6. Chart.js Dashboard Charts Initialization
  initDashboardCharts();
  initLivestockInteractions();
});

function initLivestockInteractions() {
  const table = document.getElementById('livestockTable');
  const filters = document.getElementById('livestockFilters');

  if (!table || !filters) return;

  const searchInput = document.getElementById('livestockSearch');
  const typeFilter = document.getElementById('livestockTypeFilter');
  const healthFilter = document.getElementById('livestockHealthFilter');
  const resultCount = document.getElementById('livestockResults');
  const emptyState = document.getElementById('livestockEmptyState');
  const tableBody = table.querySelector('tbody');
  const rows = Array.from(table.querySelectorAll('[data-livestock-row]'));

  const applyFilters = () => {
    const search = searchInput.value.trim().toLocaleLowerCase();
    const type = typeFilter.value;
    const health = healthFilter.value;
    let visibleCount = 0;

    rows.forEach(row => {
      const matchesSearch = row.textContent.toLocaleLowerCase().includes(search);
      const matchesType = type === 'All' || row.dataset.animalType === type;
      const matchesHealth = health === 'All' || row.dataset.healthStatus === health;
      const isVisible = matchesSearch && matchesType && matchesHealth;

      row.hidden = !isVisible;
      if (isVisible) visibleCount += 1;
    });

    emptyState.hidden = visibleCount > 0;
    if (rows.length > 0 && visibleCount === 0) {
      emptyState.querySelector('td').textContent = 'No livestock records match these filters.';
    }

    if (resultCount) {
      const recordLabel = rows.length === 1 ? 'record' : 'records';
      resultCount.textContent = `Showing ${visibleCount} of ${rows.length} livestock ${recordLabel}`;
    }
  };

  searchInput.addEventListener('input', applyFilters);
  typeFilter.addEventListener('change', applyFilters);
  healthFilter.addEventListener('change', applyFilters);
  filters.addEventListener('reset', () => window.setTimeout(applyFilters, 0));

  table.querySelectorAll('.sortable-heading').forEach(button => {
    button.addEventListener('click', () => {
      const columnIndex = Number(button.dataset.sortIndex);
      const header = button.closest('th');
      const ascending = header.getAttribute('aria-sort') !== 'ascending';
      const direction = ascending ? 1 : -1;

      table.querySelectorAll('th[aria-sort]').forEach(th => th.setAttribute('aria-sort', 'none'));
      header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');

      rows.sort((leftRow, rightRow) => {
        const leftValue = leftRow.cells[columnIndex].textContent.trim();
        const rightValue = rightRow.cells[columnIndex].textContent.trim();

        if (button.dataset.sortType === 'number') {
          const leftNumber = Number.parseFloat(leftValue.replace(/[^\d.-]/g, ''));
          const rightNumber = Number.parseFloat(rightValue.replace(/[^\d.-]/g, ''));
          const leftMissing = Number.isNaN(leftNumber);
          const rightMissing = Number.isNaN(rightNumber);

          if (leftMissing !== rightMissing) return leftMissing ? 1 : -1;
          if (leftMissing) return 0;
          return direction * (leftNumber - rightNumber);
        }

        return direction * leftValue.localeCompare(rightValue, undefined, {
          numeric: true,
          sensitivity: 'base'
        });
      });

      rows.forEach(row => tableBody.appendChild(row));
    });
  });
}

/**
 * Fetch aggregation JSON APIs and render Chart.js graphs
 */
async function initDashboardCharts() {
  const incomeExpenseCanvas = document.getElementById('incomeExpensesChart');
  const cropProdCanvas = document.getElementById('cropProductionChart');

  // Chart 1: Income vs Expenses
  if (incomeExpenseCanvas && window.Chart) {
    try {
      const res = await fetch('/api/charts/income-expenses');
      if (res.ok) {
        const data = await res.json();
        new Chart(incomeExpenseCanvas, {
          type: 'bar',
          data: {
            labels: data.labels,
            datasets: [
              {
                label: 'Income / Sales (UGX)',
                data: data.income,
                backgroundColor: 'rgba(22, 163, 74, 0.85)',
                borderColor: '#15803d',
                borderWidth: 1,
                borderRadius: 4
              },
              {
                label: 'Farm Expenses (UGX)',
                data: data.expenses,
                backgroundColor: 'rgba(239, 68, 68, 0.75)',
                borderColor: '#dc2626',
                borderWidth: 1,
                borderRadius: 4
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'top', labels: { boxWidth: 14, font: { size: 12 } } },
              tooltip: {
                callbacks: {
                  label: function(context) {
                    const val = context.parsed.y || 0;
                    return `${context.dataset.label}: UGX ${val.toLocaleString()}`;
                  }
                }
              }
            },
            scales: {
              y: {
                beginAtZero: true,
                ticks: {
                  callback: function(val) {
                    if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                    if (val >= 1000) return (val / 1000).toFixed(0) + 'K';
                    return val;
                  }
                }
              }
            }
          }
        });
      }
    } catch (err) {
      console.error('Error loading income/expenses chart:', err);
    }
  }

  // Chart 2: Crop Production by Yield
  if (cropProdCanvas && window.Chart) {
    try {
      const res = await fetch('/api/charts/crop-production');
      if (res.ok) {
        const data = await res.json();
        new Chart(cropProdCanvas, {
          type: 'doughnut',
          data: {
            labels: data.labels.length > 0 ? data.labels : ['No Harvest Data Yet'],
            datasets: [{
              data: data.data.length > 0 ? data.data : [1],
              backgroundColor: [
                '#15803d', '#10b981', '#34d399', '#6ee7b7', 
                '#d97706', '#f59e0b', '#3b82f6', '#8b5cf6'
              ],
              borderWidth: 2,
              borderColor: '#ffffff'
            }]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } },
              tooltip: {
                callbacks: {
                  label: function(context) {
                    const label = context.label || '';
                    const val = context.parsed || 0;
                    return `${label}: ${val.toLocaleString()} units`;
                  }
                }
              }
            },
            cutout: '62%'
          }
        });
      }
    } catch (err) {
      console.error('Error loading crop production chart:', err);
    }
  }
}
