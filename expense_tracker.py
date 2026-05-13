import argparse
import calendar
import csv
import json
from datetime import datetime, date, timedelta
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    from pydantic import BaseModel
    import uvicorn
    WEB_AVAILABLE = True
except ImportError:
    WEB_AVAILABLE = False

DATA_FILE = Path(__file__).parent / "expenses.json"
BUDGET_FILE = Path(__file__).parent / "budgets.json"
RECURRING_FILE = Path(__file__).parent / "recurrings.json"
DATE_FORMAT = "%Y-%m-%d"


class ExpenseCreate(BaseModel):
    date: str
    amount: float
    category: str
    description: str


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, DATE_FORMAT).date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"Date must be in YYYY-MM-DD format: {date_str}")


def load_json(path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path, data):
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def load_expenses():
    return load_json(DATA_FILE, [])


def save_expenses(expenses):
    save_json(DATA_FILE, expenses)


def load_budgets():
    return load_json(BUDGET_FILE, {})


def save_budgets(budgets):
    save_json(BUDGET_FILE, budgets)


def load_recurrings():
    return load_json(RECURRING_FILE, [])


def save_recurrings(recurrings):
    save_json(RECURRING_FILE, recurrings)


def next_id(items):
    return max((item.get("id", 0) for item in items), default=0) + 1


def add_expense(args):
    expenses = load_expenses()
    entry = {
        "id": next_id(expenses),
        "date": args.date.isoformat(),
        "amount": round(args.amount, 2),
        "category": args.category.strip(),
        "description": args.description.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    expenses.append(entry)
    save_expenses(expenses)
    print(f"Added expense {entry['id']}: {entry['amount']} {entry['category']} on {entry['date']}")


def filter_expenses(expenses, start_date=None, end_date=None, category=None):
    result = []
    for expense in expenses:
        expense_date = datetime.strptime(expense["date"], DATE_FORMAT).date()
        if start_date and expense_date < start_date:
            continue
        if end_date and expense_date > end_date:
            continue
        if category and expense["category"].lower() != category.lower():
            continue
        result.append(expense)
    return result


def print_expenses(expenses):
    if not expenses:
        print("No expenses found.")
        return
    print("ID  Date       Amount   Category      Description")
    print("--  ---------- -------- ------------- ---------------------------")
    for expense in expenses:
        print(
            f"{expense['id']:>2}  {expense['date']}  {expense['amount']:>7.2f}  "
            f"{expense['category'][:13]:<13}  {expense['description'][:27]}"
        )


def list_expenses(args):
    expenses = apply_recurring_expenses()
    filtered = filter_expenses(expenses, args.start, args.end, args.category)
    print_expenses(filtered)


def months_between(start_date, end_date):
    return (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1


def advance_date(value, frequency):
    if frequency == "daily":
        return value + timedelta(days=1)
    if frequency == "weekly":
        return value + timedelta(weeks=1)
    if frequency == "monthly":
        month = value.month + 1
        year = value.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    if frequency == "yearly":
        year = value.year + 1
        day = min(value.day, calendar.monthrange(year, value.month)[1])
        return date(year, value.month, day)
    raise ValueError(f"Unknown frequency: {frequency}")


def apply_recurring_expenses(as_of_date=None):
    if as_of_date is None:
        as_of_date = date.today()
    recurrings = load_recurrings()
    expenses = load_expenses()
    updated = False

    for recurrence in recurrings:
        frequency = recurrence.get("frequency", "monthly")
        start_date = parse_date(recurrence["start_date"])
        last_applied = parse_date(recurrence["last_applied"]) if recurrence.get("last_applied") else None
        next_date = start_date if last_applied is None else advance_date(last_applied, frequency)

        while next_date <= as_of_date:
            entry = {
                "id": next_id(expenses),
                "date": next_date.isoformat(),
                "amount": round(recurrence["amount"], 2),
                "category": recurrence["category"].strip(),
                "description": recurrence["description"].strip() + " (recurring)",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "recurrence_id": recurrence["id"],
            }
            expenses.append(entry)
            recurrence["last_applied"] = next_date.isoformat()
            next_date = advance_date(next_date, frequency)
            updated = True

    if updated:
        save_expenses(expenses)
        save_recurrings(recurrings)

    return expenses


def compute_budget_report(expenses, budgets, start_date=None, end_date=None):
    if start_date is None or end_date is None:
        now = date.today()
        start_date = date(now.year, now.month, 1)
        end_date = date(now.year, now.month, calendar.monthrange(now.year, now.month)[1])

    report = []
    for budget_category, budget_info in budgets.items():
        normalized = normalize_budget_info(budget_info)
        amount = normalized["amount"]
        period = normalized["period"]
        alert_percent = normalized.get("alert_percent", 80)
        spent = 0.0
        for expense in expenses:
            if expense["category"].lower() == budget_category.lower():
                spent += expense["amount"]

        if period == "monthly":
            total_months = months_between(start_date, end_date)
            budget_total = amount * total_months
            label = f"{amount:.2f}/month"
        else:
            budget_total = amount
            label = f"{amount:.2f}"

        remaining = budget_total - spent
        percent = (spent / budget_total * 100) if budget_total else 0.0
        alert_threshold = budget_total * alert_percent / 100 if budget_total else 0.0
        if spent > budget_total:
            status = "OVER"
        elif spent >= alert_threshold:
            status = "ALERT"
        else:
            status = "OK"

        report.append({
            "category": budget_category,
            "budget_label": label,
            "budget_total": budget_total,
            "spent": spent,
            "remaining": remaining,
            "percent": percent,
            "status": status,
            "alert_percent": alert_percent,
        })

    return sorted(report, key=lambda row: (row["status"] != "OVER", -row["spent"]))


def normalize_budget_info(budget_info):
    if isinstance(budget_info, dict):
        return {
            "amount": round(float(budget_info.get("amount", 0.0)), 2),
            "period": budget_info.get("period", "one-time") or "one-time",
            "alert_percent": round(float(budget_info.get("alert_percent", 80)), 2),
        }
    return {"amount": round(float(budget_info), 2), "period": "one-time", "alert_percent": 80}


def print_budget_summary(expenses, budgets, start_date=None, end_date=None):
    if not budgets:
        print("No budgets set. Use the budget menu or budget subcommand to add category budgets.")
        return

    report = compute_budget_report(expenses, budgets, start_date, end_date)
    print("\nBudget status:")
    print("Category       Budget       Spent   Remaining   Status")
    print("------------- ------------ -------- ----------- -------")
    for row in report:
        print(
            f"{row['category'][:13]:<13} "
            f"{row['budget_label']:>12} "
            f"{row['spent']:>7.2f} "
            f"{row['remaining']:>11.2f} "
            f"{row['status']}"
        )

    budget_categories = {key.lower() for key in budgets}
    unbudgeted = sorted({expense["category"] for expense in expenses if expense["category"].lower() not in budget_categories})
    if unbudgeted:
        print("\nUnbudgeted categories:")
        print("  " + ", ".join(unbudgeted))


def summary_expenses(args):
    expenses = apply_recurring_expenses()
    filtered = filter_expenses(expenses, args.start, args.end, args.category)
    if not filtered:
        print("No expenses found for this query.")
        return

    total = sum(item["amount"] for item in filtered)
    count = len(filtered)
    average = total / count if count else 0.0
    by_category = {}
    by_date = {}

    for item in filtered:
        by_category[item["category"]] = by_category.get(item["category"], 0.0) + item["amount"]
        by_date[item["date"]] = by_date.get(item["date"], 0.0) + item["amount"]

    print(f"Total expenses: {total:.2f}")
    print(f"Entries: {count}")
    print(f"Average per entry: {average:.2f}\n")

    print("Totals by category:")
    for category, amount in sorted(by_category.items(), key=lambda kv: -kv[1]):
        print(f"  {category}: {amount:.2f}")

    print("\nTotals by date:")
    for date_key, amount in sorted(by_date.items()):
        print(f"  {date_key}: {amount:.2f}")

    budgets = load_budgets()
    if budgets:
        print_budget_summary(filtered, budgets, args.start, args.end)


def export_expenses(args):
    expenses = apply_recurring_expenses()
    filtered = filter_expenses(expenses, args.start, args.end, args.category)
    if not filtered:
        print("No expenses to export.")
        return
    output_path = Path(args.output)
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["id", "date", "amount", "category", "description", "created_at"])
        writer.writeheader()
        writer.writerows(filtered)
    print(f"Exported {len(filtered)} expense(s) to {output_path}")


def remove_expense(args):
    expenses = load_expenses()
    remaining = [item for item in expenses if item["id"] != args.id]
    if len(remaining) == len(expenses):
        print(f"Expense ID {args.id} not found.")
        return
    for index, item in enumerate(remaining, start=1):
        item["id"] = index
    save_expenses(remaining)
    print(f"Removed expense {args.id}. Updated {len(remaining)} remaining entries.")


def budget_set(args):
    budgets = load_budgets()
    period = args.period.lower() if getattr(args, "period", None) else "one-time"
    if period not in {"one-time", "monthly"}:
        print("Period must be one-time or monthly.")
        return
    alert_percent = round(args.alert_percent, 2) if getattr(args, "alert_percent", None) is not None else 80.0
    budgets[args.category.strip()] = {
        "amount": round(args.amount, 2),
        "period": period,
        "alert_percent": alert_percent,
    }
    save_budgets(budgets)
    print(f"Set {period} budget for {args.category}: {budgets[args.category]['amount']:.2f}, alert at {alert_percent:.0f}%")


def budget_list(args):
    budgets = load_budgets()
    if not budgets:
        print("No budgets set.")
        return
    print("Category       Amount     Period    Alert")
    print("------------- ---------- -------- -------")
    for category, info in sorted(budgets.items()):
        normalized = normalize_budget_info(info)
        print(
            f"{category[:13]:<13} {normalized['amount']:>10.2f} "
            f"{normalized['period']:<7} {normalized['alert_percent']:>6.0f}%"
        )


def budget_alerts(args):
    budgets = load_budgets()
    if not budgets:
        print("No budgets set.")
        return
    expenses = apply_recurring_expenses()
    filtered = filter_expenses(expenses, args.start, args.end, args.category)
    alerts = [row for row in compute_budget_report(filtered, budgets, args.start, args.end) if row["status"] in {"ALERT", "OVER"}]
    if not alerts:
        print("No budget alerts at this time.")
        return
    print("Budget alerts:")
    print("Category       Status   Spent   Budget   Alert")
    print("------------- -------- ------- -------- -------")
    for row in alerts:
        print(
            f"{row['category'][:13]:<13} {row['status']:<7} "
            f"{row['spent']:>7.2f} {row['budget_total']:>8.2f} "
            f"{row['alert_percent']:>6.0f}%"
        )


def budget_status(args):
    budgets = load_budgets()
    if not budgets:
        print("No budgets set.")
        return
    expenses = apply_recurring_expenses()
    filtered = filter_expenses(expenses, args.start, args.end, args.category)
    if not filtered:
        print("No expenses found for this query.")
        return
    print_budget_summary(filtered, budgets, args.start, args.end)


def reset_recurring_entries(args):
    expenses = load_expenses()
    recurrings = load_recurrings()

    if not args.all and args.id is None:
        print("Provide --all or --id to reset generated recurring entries.")
        return

    if args.id is not None:
        recurrence = next((r for r in recurrings if r["id"] == args.id), None)
        if recurrence is None:
            print(f"Recurring ID {args.id} not found.")
            return
        cleaned = [expense for expense in expenses if expense.get("recurrence_id") != args.id]
        for index, expense in enumerate(cleaned, start=1):
            expense["id"] = index
        for recurrence in recurrings:
            if recurrence["id"] == args.id:
                recurrence["last_applied"] = None
        removed = len(expenses) - len(cleaned)
        save_expenses(cleaned)
        save_recurrings(recurrings)
        print(f"Reset {removed} generated entries for recurring ID {args.id}.")
        return

    if args.all:
        cleaned = [expense for expense in expenses if expense.get("recurrence_id") is None]
        for index, expense in enumerate(cleaned, start=1):
            expense["id"] = index
        for recurrence in recurrings:
            recurrence["last_applied"] = None
        removed = len(expenses) - len(cleaned)
        save_expenses(cleaned)
        save_recurrings(recurrings)
        print(f"Reset {removed} generated recurring entries for all patterns.")
        return


def add_recurring(args):
    recurrings = load_recurrings()
    entry = {
        "id": next_id(recurrings),
        "amount": round(args.amount, 2),
        "category": args.category.strip(),
        "description": args.description.strip(),
        "start_date": args.start_date.isoformat(),
        "frequency": args.frequency,
        "last_applied": None,
    }
    recurrings.append(entry)
    save_recurrings(recurrings)
    print(f"Added recurring expense {entry['id']} every {entry['frequency']} starting {entry['start_date']}")


def edit_recurring(args):
    recurrings = load_recurrings()
    target = next((item for item in recurrings if item["id"] == args.id), None)
    if target is None:
        print(f"Recurring ID {args.id} not found.")
        return

    if args.amount is not None:
        target["amount"] = round(args.amount, 2)
    if args.category is not None:
        target["category"] = args.category.strip()
    if args.description is not None:
        target["description"] = args.description.strip()
    if args.start_date is not None:
        target["start_date"] = args.start_date.isoformat()
        if target.get("last_applied") and parse_date(target["start_date"]) > parse_date(target["last_applied"]):
            target["last_applied"] = None
    if args.frequency is not None:
        target["frequency"] = args.frequency

    save_recurrings(recurrings)
    print(f"Updated recurring expense {target['id']}.")


def list_recurring(args):
    recurrings = load_recurrings()
    if not recurrings:
        print("No recurring expenses set.")
        return
    print("ID  Frequency  Start Date  Amount   Category      Description")
    print("--  ---------  ----------  ------- ------------- ---------------------------")
    for item in recurrings:
        print(
            f"{item['id']:>2}  {item['frequency']:<9} {item['start_date']}  "
            f"{item['amount']:>7.2f}  {item['category'][:13]:<13}  {item['description'][:27]}"
        )


def remove_recurring(args):
    recurrings = load_recurrings()
    remaining = [item for item in recurrings if item["id"] != args.id]
    if len(remaining) == len(recurrings):
        print(f"Recurring ID {args.id} not found.")
        return
    save_recurrings(remaining)
    print(f"Removed recurring expense {args.id}.")


def run_recurring(args):
    expenses = apply_recurring_expenses()
    print(f"Ensured recurring expenses are applied. Total stored expenses: {len(expenses)}")


def prompt_text(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw if raw else default


def prompt_float(prompt, default=None):
    while True:
        raw = prompt_text(prompt, default if default is not None else "")
        if raw == "" or raw is None:
            if default is not None:
                return default
            print("Please enter a number.")
            continue
        try:
            return round(float(raw), 2)
        except ValueError:
            print("Please enter a valid numeric value.")


def prompt_date(prompt, default=None):
    while True:
        default_text = default.isoformat() if isinstance(default, date) else default
        raw = prompt_text(prompt, default_text)
        if raw == "" or raw is None:
            return None
        try:
            return parse_date(raw)
        except argparse.ArgumentTypeError as exc:
            print(exc)


def prompt_choice(prompt, options):
    while True:
        choice = prompt_text(prompt)
        if choice and choice.lower() in options:
            return choice.lower()
        print(f"Please choose one of: {', '.join(options)}")


def menu_add_expense():
    print("\nAdd a new expense")
    amount = prompt_float("Amount")
    category = prompt_text("Category")
    description = prompt_text("Description", "")
    date_value = prompt_date("Date (YYYY-MM-DD)", date.today())
    add_expense(argparse.Namespace(amount=amount, category=category, description=description, date=date_value))


def menu_list_expenses():
    print("\nList expenses")
    start = prompt_date("Start date (YYYY-MM-DD)", None)
    end = prompt_date("End date (YYYY-MM-DD)", None)
    category = prompt_text("Category filter", None)
    list_expenses(argparse.Namespace(start=start, end=end, category=category))


def menu_summary():
    print("\nExpense summary")
    start = prompt_date("Start date (YYYY-MM-DD)", None)
    end = prompt_date("End date (YYYY-MM-DD)", None)
    category = prompt_text("Category filter", None)
    summary_expenses(argparse.Namespace(start=start, end=end, category=category))


def menu_set_budget():
    print("\nSet a category budget")
    category = prompt_text("Category")
    amount = prompt_float("Budget amount")
    period = prompt_choice("Period (one-time/monthly)", {"one-time", "monthly"})
    alert_percent = prompt_float("Alert threshold percent (default 80)", 80.0)
    budget_set(argparse.Namespace(category=category, amount=amount, period=period, alert_percent=alert_percent))


def menu_show_budgets():
    print("\nCurrent budgets")
    budget_list(argparse.Namespace())


def menu_add_recurring():
    print("\nAdd a recurring expense")
    amount = prompt_float("Amount")
    category = prompt_text("Category")
    description = prompt_text("Description", "")
    start_date = prompt_date("Start date (YYYY-MM-DD)", date.today())
    frequency = prompt_choice("Frequency (daily/weekly/monthly/yearly)", {"daily", "weekly", "monthly", "yearly"})
    add_recurring(argparse.Namespace(amount=amount, category=category, description=description, start_date=start_date, frequency=frequency))


def menu_list_recurring():
    print("\nRecurring expenses")
    list_recurring(argparse.Namespace())


def menu_edit_recurring():
    print("\nEdit a recurring expense")
    while True:
        raw_id = prompt_text("Recurring ID to edit")
        if raw_id and raw_id.isdigit():
            rec_id = int(raw_id)
            break
        print("Please enter a valid numeric ID.")
    raw_amount = prompt_text("New amount", "")
    amount = round(float(raw_amount), 2) if raw_amount else None
    category = prompt_text("New category", "") or None
    description = prompt_text("New description", "") or None
    start_date = prompt_date("New start date (YYYY-MM-DD)", None)
    frequency = prompt_text("New frequency (daily/weekly/monthly/yearly)", "")
    frequency = frequency.lower() if frequency else None
    valid_freq = {"daily", "weekly", "monthly", "yearly"}
    if frequency and frequency not in valid_freq:
        print("Invalid frequency. Skipping frequency update.")
        frequency = None
    edit_recurring(argparse.Namespace(id=rec_id, amount=amount, category=category, description=description, start_date=start_date, frequency=frequency))


def menu_reset_recurring():
    print("\nReset generated recurring entries")
    choice = prompt_choice("Reset recurring entries for (all/id)", {"all", "id"})
    if choice == "all":
        reset_recurring_entries(argparse.Namespace(all=True, id=None))
        return
    while True:
        raw_id = prompt_text("Recurring ID to reset")
        if raw_id and raw_id.isdigit():
            reset_recurring_entries(argparse.Namespace(all=False, id=int(raw_id)))
            return
        print("Please enter a valid numeric ID.")


def menu_export():
    print("\nExport expenses")
    output = prompt_text("Output file", "expenses_export.csv")
    start = prompt_date("Start date (YYYY-MM-DD)", None)
    end = prompt_date("End date (YYYY-MM-DD)", None)
    category = prompt_text("Category filter", None)
    export_expenses(argparse.Namespace(output=output, start=start, end=end, category=category))


def menu_remove_expense():
    print("\nRemove an expense")
    while True:
        raw_id = prompt_text("Expense ID to remove")
        if raw_id and raw_id.isdigit():
            remove_expense(argparse.Namespace(id=int(raw_id)))
            return
        print("Please enter a valid numeric ID.")


def menu_command(args):
    run_menu()


def run_menu():
    print("\nSimple Expense Tracker - Interactive Mode")
    print("Press Enter after each choice. Type q to quit.")

    while True:
        print("\n1) Add expense")
        print("2) List expenses")
        print("3) Show summary")
        print("4) Set budget")
        print("5) Show budgets")
        print("6) Add recurring expense")
        print("7) List recurring expenses")
        print("8) Edit recurring expense")
        print("9) Reset recurring generated entries")
        print("10) Export expenses")
        print("11) Remove expense")
        print("12) Quit")

        choice = prompt_text("Choose an option")
        if not choice:
            continue
        if choice in {"1", "a", "A"}:
            menu_add_expense()
        elif choice in {"2", "l", "L"}:
            menu_list_expenses()
        elif choice in {"3", "s", "S"}:
            menu_summary()
        elif choice in {"4", "b", "B"}:
            menu_set_budget()
        elif choice in {"5", "v", "V"}:
            menu_show_budgets()
        elif choice in {"6", "r", "R"}:
            menu_add_recurring()
        elif choice in {"7", "c", "C"}:
            menu_list_recurring()
        elif choice in {"8", "e", "E"}:
            menu_edit_recurring()
        elif choice in {"9", "r", "R"}:
            menu_reset_recurring()
        elif choice in {"10", "x", "X"}:
            menu_export()
        elif choice in {"11", "d", "D"}:
            menu_remove_expense()
        elif choice in {"12", "q", "Q"}:
            print("Goodbye!")
            break
        else:
            print("Unknown option. Please choose a number from 1 to 12.")


def build_parser():
    parser = argparse.ArgumentParser(description="Simple CLI Expense Tracker")
    subparsers = parser.add_subparsers(dest="command")

    menu = subparsers.add_parser("menu", help="Run interactive menu mode")
    menu.set_defaults(func=menu_command)

    add = subparsers.add_parser("add", help="Record a new expense")
    add.add_argument("--amount", type=float, required=True, help="Expense amount")
    add.add_argument("--category", required=True, help="Expense category")
    add.add_argument("--description", default="", help="Expense description")
    add.add_argument("--date", type=parse_date, default=date.today(), help="Expense date YYYY-MM-DD")
    add.set_defaults(func=add_expense)

    list_parser = subparsers.add_parser("list", help="List stored expenses")
    list_parser.add_argument("--start", type=parse_date, help="Start date YYYY-MM-DD")
    list_parser.add_argument("--end", type=parse_date, help="End date YYYY-MM-DD")
    list_parser.add_argument("--category", help="Filter by category")
    list_parser.set_defaults(func=list_expenses)

    summary = subparsers.add_parser("summary", help="Summarize expenses")
    summary.add_argument("--start", type=parse_date, help="Start date YYYY-MM-DD")
    summary.add_argument("--end", type=parse_date, help="End date YYYY-MM-DD")
    summary.add_argument("--category", help="Filter by category")
    summary.set_defaults(func=summary_expenses)

    export = subparsers.add_parser("export", help="Export expenses to CSV")
    export.add_argument("--output", default="expenses_export.csv", help="Output CSV file path")
    export.add_argument("--start", type=parse_date, help="Start date YYYY-MM-DD")
    export.add_argument("--end", type=parse_date, help="End date YYYY-MM-DD")
    export.add_argument("--category", help="Filter by category")
    export.set_defaults(func=export_expenses)

    remove = subparsers.add_parser("remove", help="Remove an expense by ID")
    remove.add_argument("id", type=int, help="ID of the expense to remove")
    remove.set_defaults(func=remove_expense)

    budget = subparsers.add_parser("budget", help="Manage category budgets")
    budget_sub = budget.add_subparsers(dest="subcommand", required=True)

    budget_set_parser = budget_sub.add_parser("set", help="Set a budget for a category")
    budget_set_parser.add_argument("--category", required=True, help="Budget category")
    budget_set_parser.add_argument("--amount", type=float, required=True, help="Budget amount")
    budget_set_parser.add_argument("--period", choices=["one-time", "monthly"], default="one-time", help="Budget period")
    budget_set_parser.add_argument("--alert-percent", type=float, default=80.0, help="Alert threshold percent")
    budget_set_parser.set_defaults(func=budget_set)

    budget_list_parser = budget_sub.add_parser("list", help="List category budgets")
    budget_list_parser.set_defaults(func=budget_list)

    budget_status_parser = budget_sub.add_parser("status", help="Show budget status for expenses")
    budget_status_parser.add_argument("--start", type=parse_date, help="Start date YYYY-MM-DD")
    budget_status_parser.add_argument("--end", type=parse_date, help="End date YYYY-MM-DD")
    budget_status_parser.add_argument("--category", help="Filter by category")
    budget_status_parser.set_defaults(func=budget_status)

    budget_alert_parser = budget_sub.add_parser("alerts", help="Show budgets nearing or over their threshold")
    budget_alert_parser.add_argument("--start", type=parse_date, help="Start date YYYY-MM-DD")
    budget_alert_parser.add_argument("--end", type=parse_date, help="End date YYYY-MM-DD")
    budget_alert_parser.add_argument("--category", help="Filter by category")
    budget_alert_parser.set_defaults(func=budget_alerts)

    recurring = subparsers.add_parser("recurring", help="Manage recurring expenses")
    recurring_sub = recurring.add_subparsers(dest="subcommand", required=True)

    recurring_add_parser = recurring_sub.add_parser("add", help="Add a recurring expense")
    recurring_add_parser.add_argument("--amount", type=float, required=True, help="Expense amount")
    recurring_add_parser.add_argument("--category", required=True, help="Expense category")
    recurring_add_parser.add_argument("--description", default="", help="Expense description")
    recurring_add_parser.add_argument("--start-date", type=parse_date, default=date.today(), help="Start date YYYY-MM-DD")
    recurring_add_parser.add_argument("--frequency", choices=["daily", "weekly", "monthly", "yearly"], default="monthly", help="Recurrence frequency")
    recurring_add_parser.set_defaults(func=add_recurring)

    recurring_list_parser = recurring_sub.add_parser("list", help="List recurring expenses")
    recurring_list_parser.set_defaults(func=list_recurring)

    recurring_edit_parser = recurring_sub.add_parser("edit", help="Edit a recurring expense")
    recurring_edit_parser.add_argument("id", type=int, help="ID of the recurring expense to edit")
    recurring_edit_parser.add_argument("--amount", type=float, help="New expense amount")
    recurring_edit_parser.add_argument("--category", help="New expense category")
    recurring_edit_parser.add_argument("--description", help="New description")
    recurring_edit_parser.add_argument("--start-date", type=parse_date, help="New start date YYYY-MM-DD")
    recurring_edit_parser.add_argument("--frequency", choices=["daily", "weekly", "monthly", "yearly"], help="New recurrence frequency")
    recurring_edit_parser.set_defaults(func=edit_recurring)

    recurring_remove_parser = recurring_sub.add_parser("remove", help="Remove a recurring expense by ID")
    recurring_remove_parser.add_argument("id", type=int, help="ID of the recurring expense to remove")
    recurring_remove_parser.set_defaults(func=remove_recurring)

    recurring_reset_parser = recurring_sub.add_parser("reset", help="Remove generated recurring expense entries")
    recurring_reset_parser.add_argument("--id", type=int, help="Recurring pattern ID to reset")
    recurring_reset_parser.add_argument("--all", action="store_true", help="Reset generated entries for all recurring patterns")
    recurring_reset_parser.set_defaults(func=reset_recurring_entries)

    recurring_run_parser = recurring_sub.add_parser("run", help="Apply due recurring expenses")
    recurring_run_parser.set_defaults(func=run_recurring)

    return parser


if WEB_AVAILABLE:
    app = FastAPI(title="Expense Tracker API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # For demo purposes
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from fastapi.responses import FileResponse

    @app.get("/")
    def read_root():
        return FileResponse("index.html")

    app.mount("/static", StaticFiles(directory="."), name="static")

    @app.get("/expenses")
    def get_expenses():
        expenses = apply_recurring_expenses()
        return expenses

    @app.post("/expenses")
    def create_expense(expense: ExpenseCreate):
        expenses = load_expenses()
        entry = {
            "id": next_id(expenses),
            "date": expense.date,
            "amount": round(expense.amount, 2),
            "category": expense.category.strip(),
            "description": expense.description.strip(),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        expenses.append(entry)
        save_expenses(expenses)
        return entry


def main():
    parser = build_parser()
    args = parser.parse_args()
    if WEB_AVAILABLE and not getattr(args, "command", None):
        # Run web server if no command specified
        uvicorn.run(app, host="0.0.0.0", port=8000)
    elif not getattr(args, "command", None):
        run_menu()
    else:
        if args.command != "menu":
            apply_recurring_expenses()
        args.func(args)


if __name__ == "__main__":
    main()
