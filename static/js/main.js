/**
 * ROYAL LEDGER - Unified Frontend Controller
 * Manages states across Index, Income, Expense, History, Weekly, and Monthly reports.
 */

document.addEventListener('DOMContentLoaded', () => {
    
    // ==========================================
    // 1. DATE PICKER CONFIGURATION (Block Yesterday)
    // ==========================================
    const dateInput = document.getElementById('date');
    if (dateInput) {
        const todayStr = new Date().toISOString().split('T')[0];
        dateInput.min = todayStr;  // Enforces calendar range validation visually
        dateInput.value = todayStr; // Defaults form selection to today
    }

    // ==========================================
    // 2. FORM RESET / INTERACTIVE BUTTON LOGIC
    // ==========================================
    const clearBtn = document.getElementById('clear-btn');
    const transactionForm = document.getElementById('transaction-form');
    if (clearBtn && transactionForm) {
        clearBtn.addEventListener('click', () => {
            transactionForm.reset();
            if (dateInput) {
                dateInput.value = new Date().toISOString().split('T')[0];
            }
        });
    }

    // ==========================================
    // 3. DYNAMIC CATEGORY LOGIC (Saved Locally)
    // ==========================================
    let defaultIncomeCategories = ['Salary', 'Freelance', 'Investments'];
    let defaultExpenseCategories = ['Food', 'Rent', 'Milk Cost', 'Electricity', 'Fuel'];

    // Retrieve customized entries or fallback to standard system values
    let incomeCategories = JSON.parse(localStorage.getItem('incomeCats')) || defaultIncomeCategories;
    let expenseCategories = JSON.parse(localStorage.getItem('expenseCats')) || defaultExpenseCategories;

    function updateCategoryLists() {
        const incomeList = document.getElementById('income-categories');
        const expenseList = document.getElementById('expense-categories');
        if (incomeList) {
            incomeList.innerHTML = incomeCategories.map(c => `<option value="${c}">`).join('');
        }
        if (expenseList) {
            expenseList.innerHTML = expenseCategories.map(c => `<option value="${c}">`).join('');
        }
    }

    // Initial load setup for custom text inputs
    updateCategoryLists();

    // ==========================================
    // 4. API TRANSACTION SUBMISSION (POST)
    // ==========================================
    // ==========================================
    // 4. API TRANSACTION SUBMISSION (POST)
    // ==========================================
    if (transactionForm) {
        transactionForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const type = transactionForm.dataset.type;
            
            // Safe selector targeting to prevent errors if elements are missing
            const amtEl = document.getElementById('amount');
            const catEl = document.getElementById('category');
            const dateEl = document.getElementById('date');
            const noteEl = document.getElementById('note');

            const amount = amtEl ? amtEl.value : 0;
            const category = catEl ? catEl.value.trim() : 'General';
            const date = dateEl ? dateEl.value : new Date().toISOString().split('T')[0];
            const note = noteEl ? noteEl.value : '';

            try {
                // Submit object map directly to Flask database endpoint
                const response = await fetch('/api/transactions', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type, amount, category, date, note })
                });

                const result = await response.json();

                if (response.ok) {
                    alert("Transaction logged perfectly!");
                    
                    // Track dynamic categories instantly if it is a newly discovered unique variation
                    if (type === 'income' && !incomeCategories.includes(category)) {
                        incomeCategories.push(category);
                        localStorage.setItem('incomeCats', JSON.stringify(incomeCategories));
                    } else if (type === 'expense' && !expenseCategories.includes(category)) {
                        expenseCategories.push(category);
                        localStorage.setItem('expenseCats', JSON.stringify(expenseCategories));
                    }
                    
                    transactionForm.reset();
                    if (dateInput) dateInput.value = new Date().toISOString().split('T')[0];
                    updateCategoryLists();
                    renderDataGraphics(); // This forces the table side to reload instantly!
                } else {
                    // Handles server-side errors like yesterday's date block
                    alert(`Error Blocked: ${result.message || 'Unknown Server Error'}`);
                }
            } catch (err) {
                console.error("Fetch communication failed:", err);
                alert("Could not connect to the backend server.");
            }
        });
    }
    // ==========================================
    // 5. DATA RENDERING & REPORT ENGINE (GET)
    // ==========================================
    async function renderDataGraphics() {
        // Structural verify flags checking whether tracking metrics exist inside page DOM layout
        const hasTextDisplays = document.querySelector('.amount-display');
        const hasTables = document.querySelector('table');
        const hasCharts = document.querySelector('canvas');
        if (!hasTextDisplays && !hasTables && !hasCharts) return;

        // Fetch transaction stream arrays from DB integration routes
        const res = await fetch('/api/transactions');
        const transactions = await res.json();

        // Separate specific datasets
        let incomeRecords = transactions.filter(t => t.type === 'income');
        let expenseRecords = transactions.filter(t => t.type === 'expense');

        // ==========================================
        // REFRESH LOCAL INCOME TABLE DATA
        // ==========================================
        const incTableBody = document.querySelector('#local-income-table tbody');
        if (incTableBody) {
            incTableBody.innerHTML = ''; // Wipe clean before painting
            if (incomeRecords.length === 0) {
                incTableBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No recorded income data.</td></tr>`;
            } else {
                incomeRecords.forEach((t, index) => {
                    const row = `<tr>
                        <td>${index + 1}</td>
                        <td style="color: var(--income-green); font-weight: bold;">₹${parseFloat(t.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        <td>${t.category}</td>
                        <td>${t.date}</td>
                    </tr>`;
                    incTableBody.innerHTML += row;
                });
            }
        }

        // ==========================================
        // REFRESH LOCAL EXPENSE TABLE DATA
        // ==========================================
        const expTableBody = document.querySelector('#local-expense-table tbody');
        if (expTableBody) {
            expTableBody.innerHTML = ''; // Wipe clean before painting
            if (expenseRecords.length === 0) {
                expTableBody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No recorded expense data.</td></tr>`;
            } else {
                expenseRecords.forEach((t, index) => {
                    const row = `<tr>
                        <td>${index + 1}</td>
                        <td style="color: var(--expense-red); font-weight: bold;">₹${parseFloat(t.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                        <td>${t.category}</td>
                        <td>${t.date}</td>
                    </tr>`;
                    expTableBody.innerHTML += row;
                });
            }
        }

        // ==========================================
        // PARSE GLOBAL METRICS & AGGREGATIONS
        // ==========================================
        let totalIncome = 0;
        let totalExpense = 0;
        const dailyData = {};
        const expenseCategoryTotals = {};

        transactions.forEach(t => {
            if (t.type === 'income') {
                totalIncome += t.amount;
            } else {
                totalExpense += t.amount;
                // Accumulate unique category metrics for breakdowns
                expenseCategoryTotals[t.category] = (expenseCategoryTotals[t.category] || 0) + t.amount;
            }
            
            // Build historical structures grouped chronologically
            if (!dailyData[t.date]) dailyData[t.date] = { income: 0, expense: 0 };
            dailyData[t.date][t.type] += t.amount;
        });

        // Calculate Net Available Value
        let availableBalance = totalIncome - totalExpense;

        // Target text DOM dashboard fields
        const incDisplay = document.querySelector('.amount-display.income');
        const expDisplay = document.querySelector('.amount-display.expense');
        const balDisplay = document.querySelector('.amount-display.available-balance');

        if (incDisplay) incDisplay.innerText = `₹${totalIncome.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        if (expDisplay) expDisplay.innerText = `₹${totalExpense.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        
        if (balDisplay) {
            balDisplay.innerText = `₹${availableBalance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            
            // Contextual color configurations for balance tracking
            if (availableBalance > 0) {
                balDisplay.style.color = 'var(--income-green)';
            } else if (availableBalance < 0) {
                balDisplay.style.color = 'var(--expense-red)';
            } else {
                balDisplay.style.color = 'var(--accent-gold)';
            }
        }

        // ==========================================
        // GLOBAL CHRONOLOGICAL HISTORY PAGE TABLE VIEW
        // ==========================================
        const globalTableBody = document.querySelector('table:not(#local-income-table):not(#local-expense-table) tbody');
        if (globalTableBody) {
            if (transactions.length === 0) {
                globalTableBody.innerHTML = `<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">Ledger Empty.</td></tr>`;
            } else {
                globalTableBody.innerHTML = transactions.map(t => `
                    <tr>
                        <td>${t.date}</td>
                        <td>${t.category}</td>
                        <td style="color: ${t.type === 'income' ? 'var(--income-green)' : 'var(--expense-red)'}">${t.type.toUpperCase()}</td>
                        <td>${t.note || '-'}</td>
                        <td style="color: ${t.type === 'income' ? 'var(--income-green)' : 'var(--expense-red)'}">₹${t.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                    </tr>
                `).join('');
            }
        }

        // ==========================================
        // DATA VISUALIZATION GRAPH COMPILATION ENGINE
        // ==========================================
        const sortedDates = Object.keys(dailyData).sort().slice(-7); // Extract trailing week timestamps

        // Index Page Bar Graph
        if (document.getElementById('dashboardDailyChart')) {
            new Chart(document.getElementById('dashboardDailyChart'), {
                type: 'bar',
                data: {
                    labels: sortedDates.length ? sortedDates : ['No Data Available'],
                    datasets: [
                        { label: 'Income', data: sortedDates.map(d => dailyData[d].income), backgroundColor: '#2ecc71' },
                        { label: 'Expense', data: sortedDates.map(d => dailyData[d].expense), backgroundColor: '#e74c3c' }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        // Weekly Progress Trends (Trend Curve)
        if (document.getElementById('weeklyReportChart')) {
            new Chart(document.getElementById('weeklyReportChart'), {
                type: 'line',
                data: {
                    labels: sortedDates.length ? sortedDates : ['Waiting for entries...'],
                    datasets: [{ 
                        label: 'Net Saving Activity Index', 
                        data: sortedDates.map(d => (dailyData[d].income - dailyData[d].expense)), 
                        borderColor: '#C5A059', 
                        tension: 0.2,
                        fill: false
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }

        // Monthly Resource Categorization Report (Donut Graphic)
        if (document.getElementById('monthlyReportChart')) {
            const keys = Object.keys(expenseCategoryTotals);
            new Chart(document.getElementById('monthlyReportChart'), {
                type: 'doughnut',
                data: {
                    labels: keys.length ? keys : ['No Expenses Tracked'],
                    datasets: [{
                        data: keys.length ? Object.values(expenseCategoryTotals) : [1],
                        backgroundColor: ['#C5A059', '#34495E', '#E74C3C', '#2ECC71', '#9B59B6', '#F1C40F']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        }
    }

    // Run active data processing algorithms automatically on window layout changes
    renderDataGraphics();
});
// Fetch and display the highest categories for the Weekly View
function loadWeeklyTopCategories() {
    fetch('/api/top-categories?range=weekly')
        .then(response => response.json())
        .then(data => {
            // Update the HTML text elements dynamically
            const topExpenseEl = document.getElementById('weekly-top-expense-cat');
            const topIncomeEl = document.getElementById('weekly-top-income-cat');
            
            if (topExpenseEl) {
                topExpenseEl.innerText = data.top_expense ? `${data.top_expense.category} (₹${data.top_expense.amount.toFixed(2)})` : "None";
            }
            if (topIncomeEl) {
                topIncomeEl.innerText = data.top_income ? `${data.top_income.category} (₹${data.top_income.amount.toFixed(2)})` : "None";
            }
        })
        .catch(error => console.error('Error fetching weekly top categories:', error));
}

// Fetch and display the highest categories for the Monthly View
function loadMonthlyTopCategories() {
    fetch('/api/top-categories?range=monthly')
        .then(response => response.json())
        .then(data => {
            const topExpenseEl = document.getElementById('monthly-top-expense-cat');
            const topIncomeEl = document.getElementById('monthly-top-income-cat');
            
            if (topExpenseEl) {
                topExpenseEl.innerText = data.top_expense ? `${data.top_expense.category} (₹${data.top_expense.amount.toFixed(2)})` : "None";
            }
            if (topIncomeEl) {
                topIncomeEl.innerText = data.top_income ? `${data.top_income.category} (₹${data.top_income.amount.toFixed(2)})` : "None";
            }
        })
        .catch(error => console.error('Error fetching monthly top categories:', error));
}

// Automatically trigger data loading when the page finishes loading
document.addEventListener('DOMContentLoaded', () => {
    loadWeeklyTopCategories();
    loadMonthlyTopCategories();
}); 

function updateDashboardClock() {
    const clockEl = document.getElementById('live-clock');
    if (clockEl) {
        const now = new Date();
        clockEl.innerText = now.toLocaleTimeString();
    }
}
setInterval(updateDashboardClock, 1000);
document.addEventListener('DOMContentLoaded', updateDashboardClock);


  