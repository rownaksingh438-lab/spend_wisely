# SpendSmart — Full-Stack Version

The original SpendSmart was a **frontend-only** page: cards, expenses and bills lived in
the browser's `localStorage`, the rewards numbers (2,500 points / ₹1,250 cashback) were
typed into the HTML by hand, and there was no login — so data vanished with the browser
and nothing was ever computed by a server.

This version keeps the **same design and pages** but connects everything to a **real
backend** (Python Flask + SQLite database):

## What is real now

| Feature | Before (frontend only) | Now (full-stack) |
|---|---|---|
| Login / Register | Not present | Real accounts, passwords stored as salted PBKDF2 hashes |
| Cards | 6 cards hard-coded in HTML + localStorage | Stored in database per user; add/delete works |
| Expenses | localStorage | Database, with server-side validation |
| Bills | localStorage | Database; Mark Paid/Pending updates the server |
| Dashboard totals | Calculated in the browser | `GET /api/dashboard` — computed by the server |
| Rewards | Fixed text: "2,500 Points", "₹1,250" | Computed from your real data (rules below) |
| Insights | Calculated in the browser | `GET /api/insights` — category totals from the database |
| Data safety | Lost when browser data is cleared | Saved in `spendsmart.db`; works from any browser after login |

## Reward rules (computed by the backend)

- **Reward Points:** 1 point for every ₹100 of total expenses.
- **Estimated Cashback:** for every expense paid with a card whose reward text names a
  cashback percentage (e.g. "5% Cashback"), cashback = that % of the expense amount.
- **Travel Benefits:** "Available" if you hold any card whose reward mentions Travel.

## Demo (seed) data

A **new account** is automatically filled with demo data so the app can be seen working
immediately: the same 6 bank cards as the original design, 6 sample expenses and 2 sample
bills. Every item can be deleted from the UI — it is normal database data, nothing is
hard-coded any more.

## How to run

```
pip install -r requirements.txt
```

```
python app.py
```

Then open **http://127.0.0.1:5000** in a browser → Register a new account → the app opens
with the demo data. After that, Login works from any browser on this machine, and all
changes are saved in `spendsmart.db` (created automatically next to `app.py`).

To start completely fresh, stop the server and delete `spendsmart.db`.

## Project structure

```
app.py                 Flask backend: auth + REST APIs + SQLite (all in one file)
requirements.txt       Only one dependency: flask
static/index.html      The original SpendSmart design, wired to the API
static/style.css       Original styles + small additions for the login screen
static/script.js       Frontend logic — every action is an API call
spendsmart.db          Database file (auto-created on first run)
```

## API list

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/register` | Create account (seeds demo data), logs in |
| POST | `/api/login` | Login |
| POST | `/api/logout` | Logout |
| GET | `/api/me` | Current login state |
| GET / POST / DELETE | `/api/cards`, `/api/cards/<id>` | List / add / delete cards |
| GET / POST / DELETE | `/api/expenses`, `/api/expenses/<id>` | List / add / delete expenses |
| GET / POST / DELETE | `/api/bills`, `/api/bills/<id>` | List / add / delete bills |
| PATCH | `/api/bills/<id>/toggle` | Mark bill Paid ↔ Pending |
| GET | `/api/dashboard` | Total expenses, card count, reward points, pending bills |
| GET | `/api/insights` | Category-wise totals (Food / Shopping / Travel / Other) |
| GET | `/api/rewards` | Points, estimated cashback, travel benefit status |
