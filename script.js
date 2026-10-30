// SpendSmart — Full-Stack Frontend
// All data comes from the Flask backend (SQLite database) through the /api routes.
// Nothing is stored in localStorage any more.

let cards = [];
let expenses = [];
let bills = [];

// ---------- helpers ----------
async function api(path, options = {}) {
    const res = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    let data = {};
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (!res.ok) {
        throw new Error(data.error || "Something went wrong");
    }
    return data;
}

function esc(text) {
    return String(text ?? "")
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function fmt(amount) {
    return "₹" + Number(amount).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

// ---------- auth ----------
async function checkAuth() {
    try {
        const me = await api("/api/me");
        if (me.logged_in) {
            enterApp(me.username);
        }
    } catch (e) { /* stay on auth screen */ }
}

async function doLogin() {
    const username = document.getElementById("authUsername").value.trim();
    const password = document.getElementById("authPassword").value;
    try {
        const res = await api("/api/login", {
            method: "POST",
            body: JSON.stringify({ username, password }),
        });
        enterApp(res.username);
    } catch (e) {
        alert(e.message);
    }
}

async function doRegister() {
    const username = document.getElementById("authUsername").value.trim();
    const password = document.getElementById("authPassword").value;
    try {
        const res = await api("/api/register", {
            method: "POST",
            body: JSON.stringify({ username, password }),
        });
        enterApp(res.username);
    } catch (e) {
        alert(e.message);
    }
}

async function doLogout() {
    await api("/api/logout", { method: "POST" });
    location.reload();
}

function enterApp(username) {
    document.getElementById("authScreen").style.display = "none";
    document.getElementById("appShell").style.display = "block";
    document.querySelectorAll(".userNameLabel").forEach(function (el) {
        el.innerText = username;
    });
    loadAll();
}

// ---------- page switching ----------
function showPage(pageName) {
    document.querySelectorAll(".page").forEach(function (page) {
        page.classList.remove("active");
    });
    document.getElementById(pageName).classList.add("active");
    updateDashboard();
    updateInsights();
    updateRewards();
}

// ---------- load everything ----------
async function loadAll() {
    try {
        cards = await api("/api/cards");
        expenses = await api("/api/expenses");
        bills = await api("/api/bills");
        displayCards();
        displayExpenses();
        displayBills();
        updateDashboard();
        updateInsights();
        updateRewards();
    } catch (e) {
        alert(e.message);
    }
}

// ---------- cards ----------
function displayCards() {
    const knownThemes = ["hdfc", "sbi", "axis", "icici", "amazon", "kotak"];
    let output = "";
    cards.forEach(function (card) {
        const theme = knownThemes.includes(card.theme) ? card.theme : "custom";
        output += `
            <div class="bank-card ${theme}">
                <span>${esc(card.bank || "MY CARD")}</span>
                <h3>${esc(card.name)}</h3>
                <div class="chip">▦</div>
                <p>Credit Limit</p>
                <h2>${fmt(card.credit_limit)}</h2>
                <small>Reward: ${esc(card.reward)}</small><br>
                <button class="delete-btn" onclick="deleteCard(${card.id})">Delete</button>
            </div>
        `;
    });
    document.getElementById("cardList").innerHTML =
        output || "<p>No cards yet — add your first card below.</p>";

    // Payment methods in the expense form = user's cards + Cash
    const select = document.getElementById("paymentMethod");
    const previous = select.value;
    select.innerHTML = cards.map(function (card) {
        return `<option value="${esc(card.name)}">${esc(card.name)}</option>`;
    }).join("") + `<option value="Cash">Cash</option>`;
    if (previous) select.value = previous;

    // Benefits table on the Rewards page
    document.getElementById("benefitsList").innerHTML = cards.map(function (card) {
        return `<tr><td>${esc(card.name)}</td><td>${esc(card.reward)}</td></tr>`;
    }).join("");
}

async function addCard() {
    const name = document.getElementById("cardName").value.trim();
    const limit = document.getElementById("cardLimit").value;
    const reward = document.getElementById("cardReward").value.trim();
    if (!name || !limit || !reward) {
        alert("Please fill all card details");
        return;
    }
    try {
        await api("/api/cards", {
            method: "POST",
            body: JSON.stringify({ name, limit: Number(limit), reward }),
        });
        document.getElementById("cardName").value = "";
        document.getElementById("cardLimit").value = "";
        document.getElementById("cardReward").value = "";
        cards = await api("/api/cards");
        displayCards();
        updateDashboard();
    } catch (e) {
        alert(e.message);
    }
}

async function deleteCard(id) {
    try {
        await api("/api/cards/" + id, { method: "DELETE" });
        cards = await api("/api/cards");
        displayCards();
        updateDashboard();
        updateRewards();
    } catch (e) {
        alert(e.message);
    }
}

// ---------- expenses ----------
function displayExpenses() {
    let output = "";
    expenses.forEach(function (expense) {
        output += `
            <tr>
                <td>${esc(expense.name)}</td>
                <td>${fmt(expense.amount)}</td>
                <td>${esc(expense.category)}</td>
                <td>${esc(expense.payment)}</td>
                <td>${esc(expense.date)}</td>
                <td>
                    <button class="delete-btn" onclick="deleteExpense(${expense.id})">Delete</button>
                </td>
            </tr>
        `;
    });
    document.getElementById("expenseList").innerHTML = output;
}

async function addExpense() {
    const name = document.getElementById("expenseName").value.trim();
    const amount = Number(document.getElementById("expenseAmount").value);
    const category = document.getElementById("expenseCategory").value;
    const payment = document.getElementById("paymentMethod").value;
    const date = document.getElementById("expenseDate").value;
    if (!name || amount <= 0 || !date) {
        alert("Please enter valid expense details");
        return;
    }
    try {
        await api("/api/expenses", {
            method: "POST",
            body: JSON.stringify({ name, amount, category, payment, date }),
        });
        document.getElementById("expenseName").value = "";
        document.getElementById("expenseAmount").value = "";
        document.getElementById("expenseDate").value = "";
        expenses = await api("/api/expenses");
        displayExpenses();
        updateDashboard();
        updateInsights();
        updateRewards();
    } catch (e) {
        alert(e.message);
    }
}

async function deleteExpense(id) {
    try {
        await api("/api/expenses/" + id, { method: "DELETE" });
        expenses = await api("/api/expenses");
        displayExpenses();
        updateDashboard();
        updateInsights();
        updateRewards();
    } catch (e) {
        alert(e.message);
    }
}

// ---------- bills ----------
function displayBills() {
    let output = "";
    bills.forEach(function (bill) {
        const statusClass = bill.status === "Paid" ? "paid" : "pending";
        output += `
            <tr>
                <td>${esc(bill.name)}</td>
                <td>${fmt(bill.amount)}</td>
                <td>${fmt(bill.minimum)}</td>
                <td>${esc(bill.date)}</td>
                <td class="${statusClass}">${esc(bill.status)}</td>
                <td>
                    <button onclick="changeBillStatus(${bill.id})">
                        ${bill.status === "Paid" ? "Mark Pending" : "Mark Paid"}
                    </button>
                    <button class="delete-btn" onclick="deleteBill(${bill.id})">Delete</button>
                </td>
            </tr>
        `;
    });
    document.getElementById("billList").innerHTML = output;
}

async function addBill() {
    const name = document.getElementById("billName").value.trim();
    const amount = Number(document.getElementById("billAmount").value);
    const minimum = Number(document.getElementById("minimumAmount").value);
    const date = document.getElementById("billDate").value;
    if (!name || amount <= 0 || minimum < 0 || !date) {
        alert("Please enter valid bill details");
        return;
    }
    if (minimum > amount) {
        alert("Minimum payable cannot be greater than total amount");
        return;
    }
    try {
        await api("/api/bills", {
            method: "POST",
            body: JSON.stringify({ name, amount, minimum, date }),
        });
        document.getElementById("billName").value = "";
        document.getElementById("billAmount").value = "";
        document.getElementById("minimumAmount").value = "";
        document.getElementById("billDate").value = "";
        bills = await api("/api/bills");
        displayBills();
        updateDashboard();
    } catch (e) {
        alert(e.message);
    }
}

async function changeBillStatus(id) {
    try {
        await api("/api/bills/" + id + "/toggle", { method: "PATCH" });
        bills = await api("/api/bills");
        displayBills();
        updateDashboard();
    } catch (e) {
        alert(e.message);
    }
}

async function deleteBill(id) {
    try {
        await api("/api/bills/" + id, { method: "DELETE" });
        bills = await api("/api/bills");
        displayBills();
        updateDashboard();
    } catch (e) {
        alert(e.message);
    }
}

// ---------- computed views (server-side) ----------
async function updateDashboard() {
    if (document.getElementById("appShell").style.display === "none") return;
    try {
        const d = await api("/api/dashboard");
        document.getElementById("totalExpenses").innerText = fmt(d.total_expenses);
        document.getElementById("totalCards").innerText = d.total_cards;
        document.getElementById("totalRewards").innerText = d.reward_points + " Points";
        document.getElementById("pendingBills").innerText = d.pending_bills;
    } catch (e) { /* not logged in yet */ }
}

async function updateInsights() {
    if (document.getElementById("appShell").style.display === "none") return;
    try {
        const d = await api("/api/insights");
        document.getElementById("foodTotal").innerText = fmt(d.food);
        document.getElementById("shoppingTotal").innerText = fmt(d.shopping);
        document.getElementById("travelTotal").innerText = fmt(d.travel);
        document.getElementById("otherTotal").innerText = fmt(d.other);
    } catch (e) { /* not logged in yet */ }
}

async function updateRewards() {
    if (document.getElementById("appShell").style.display === "none") return;
    try {
        const d = await api("/api/rewards");
        document.getElementById("rewardPoints").innerText = d.points;
        document.getElementById("rewardCashback").innerText = fmt(d.cashback);
        document.getElementById("travelBenefits").innerText = d.travel_benefits;
    } catch (e) { /* not logged in yet */ }
}

// ---------- start ----------
checkAuth();
