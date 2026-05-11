# Simple Expense Tracker CLI

This repository contains a simple command-line expense tracker written in Python.
It stores expenses in a local JSON file and supports adding, listing, summarizing, exporting, and removing expenses.

## Requirements

- Python 3.8+

## Usage

Run the tracker from the workspace folder:

```bash
python expense_tracker.py            # start the interactive menu
python expense_tracker.py menu       # start the interactive menu
python expense_tracker.py add --amount 15.50 --category food --description "Lunch" --date 2026-05-11
python expense_tracker.py list --start 2026-05-01 --end 2026-05-11
python expense_tracker.py summary --start 2026-05-01 --end 2026-05-11
python expense_tracker.py budget set --category food --amount 300 --period monthly --alert-percent 80
python expense_tracker.py budget list
python expense_tracker.py budget status --start 2026-05-01 --end 2026-05-11
python expense_tracker.py budget alerts --start 2026-05-01 --end 2026-05-11
python expense_tracker.py recurring add --amount 29.99 --category subscription --description "Streaming" --start-date 2026-05-15 --frequency monthly
python expense_tracker.py recurring list
python expense_tracker.py recurring edit 1 --amount 34.99 --frequency yearly
python expense_tracker.py recurring reset --id 1
python expense_tracker.py recurring reset --all
python expense_tracker.py recurring run
python expense_tracker.py export --output report.csv --start 2026-05-01 --end 2026-05-11
python expense_tracker.py remove 2
```

## Commands

- `menu`: Start the interactive, menu-driven tracker.
- `add`: Add a new expense.
- `list`: Display stored expenses, optionally filtered by date range or category.
- `summary`: Show totals, average, and breakdowns by category and date.
- `budget set`: Assign a spending budget to a category, including `--period monthly`.
- `budget list`: Show category budgets.
- `budget status`: Compare filtered spending with budgets and monthly budget periods.
- `budget alerts`: Show budgets that are near or over the alert threshold.
- `recurring add`: Add a recurring expense pattern.
- `recurring list`: Show recurring expense definitions.
- `recurring edit`: Update an existing recurring expense.
- `recurring reset`: Remove generated recurring entries and reset recurrence progress.
- `recurring run`: Apply due recurring expenses to the expense history.
- `export`: Export filtered expenses to CSV.
- `remove`: Remove an expense by ID.

## Data Storage

Expenses are saved in `expenses.json` located next to `expense_tracker.py`.
