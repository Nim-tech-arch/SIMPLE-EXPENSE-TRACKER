# Simple Expense Tracker

A small expense tracker with both a CLI interface and a minimal web frontend.
Expenses are stored in `expenses.json`, and the project also supports budgets and recurring expenses.

## Requirements

- Python 3.8+

## Installation

Install the required Python packages:

```bash
pip install -r requirements.txt
```

## CLI Usage

Start the interactive CLI menu:

```bash
python expense_tracker.py
```

Use subcommands directly:

```bash
python expense_tracker.py add --amount 10.00 --category food --description lunch --date 2026-05-11
python expense_tracker.py list
python expense_tracker.py summary --start 2026-05-01 --end 2026-05-11
python expense_tracker.py export --output report.csv --start 2026-05-01 --end 2026-05-11
python expense_tracker.py remove 2
```

Budget commands:

```bash
python expense_tracker.py budget set --category food --amount 300 --period monthly --alert-percent 80
python expense_tracker.py budget list
python expense_tracker.py budget status --start 2026-05-01 --end 2026-05-11
python expense_tracker.py budget alerts --start 2026-05-01 --end 2026-05-11
```

Recurring expense commands:

```bash
python expense_tracker.py recurring add --amount 29.99 --category subscription --description "Streaming" --start-date 2026-05-15 --frequency monthly
python expense_tracker.py recurring list
python expense_tracker.py recurring edit 1 --amount 34.99 --frequency yearly
python expense_tracker.py recurring reset --id 1
python expense_tracker.py recurring reset --all
python expense_tracker.py recurring run
```

## Web Usage

Run the web server:

```bash
python expense_tracker.py
```

Then open:

```bash
http://localhost:8000
```

The web interface includes:
- Add expense form
- Load expenses button
- Dynamic total display

## API

- `GET /expenses` — retrieve all stored expenses
- `POST /expenses` — add a new expense

Request body for `POST /expenses`:

```json
{
  "date": "2026-05-13",
  "amount": 12.50,
  "category": "food",
  "description": "Lunch"
}
```

## Commands Overview

- `menu` — start the interactive menu
- `add` — add a new expense
- `list` — list stored expenses
- `summary` — show total and breakdowns
- `export` — export expenses to CSV
- `remove` — remove an expense by ID
- `budget set` / `budget list` / `budget status` / `budget alerts`
- `recurring add` / `recurring list` / `recurring edit` / `recurring reset` / `recurring run`

## Data Storage

<<<<<<< HEAD
Expenses are saved in `expenses.json` next to `expense_tracker.py`.
Recurring patterns are saved in `recurrings.json` and budgets are saved in `budgets.json`.

## Notes

This repository is intended as a small full-stack demo with both local JSON-backed persistence and a simple browser-based frontend.
=======
Expenses are saved in `expenses.json` located next to `expense_tracker.py`.
>>>>>>> c5f1da3bf79a565ce8b7b835ee0873bafc0069e7
