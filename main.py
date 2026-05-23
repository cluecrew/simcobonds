from js import document, localStorage, alert
from pyodide.ffi import create_proxy

default_rates = {
    "AAA": 3.548, "AA+": 6.975, "AA": 7.138, "AA-": 8.120,
    "A+": 8.827, "A": 10.132, "A-": 11.126,
    "BBB+": 11.753, "BBB": 12.604, "BBB-": 12.707,
    "BB+": 15.543, "BB": 19.509, "BB-": 24.997,
    "B+": 25.435, "B": 25.305, "B-": 24.342,
    "C": 31.774, "D": 36.666
}

recovery_rates = {
    "AAA": 60, "AA+": 56, "AA": 52, "AA-": 48,
    "A+": 44, "A": 40, "A-": 36,
    "BBB+": 32, "BBB": 28, "BBB-": 24,
    "BB+": 20, "BB": 16, "BB-": 12,
    "B+": 4, "B": 4, "B-": 4, "C": 4, "D": 4
}

rating_order = {
    "AAA": 18, "AA+": 17, "AA": 16, "AA-": 15,
    "A+": 14, "A": 13, "A-": 12,
    "BBB+": 11, "BBB": 10, "BBB-": 9,
    "BB+": 8, "BB": 7, "BB-": 6,
    "B+": 5, "B": 4, "B-": 3,
    "C": 2, "D": 1
}

columns = [
    "Company", "Rating", "Rating at Purchase", "Interest Rate", "Amount",
    "Callable (Days)", "Default Rate %", "Recovery rate %", "Recovery Value ($)"
]

numeric_columns = {
    "Interest Rate", "Amount", "Callable (Days)",
    "Default Rate %", "Recovery rate %", "Recovery Value ($)"
}

rows = []
sort_reverse = {}


def money(value):
    return f"${value:,.0f}"


def pct(value):
    return f"{value:.2f}%"


def parse_callable(text):
    text = text.lower()

    if "in" not in text:
        return 0

    try:
        part = text.split("in")[-1].strip()

        if "w" in part:
            return int(part.replace("w", "")) * 7

        if "d" in part:
            return int(part.replace("d", ""))

    except Exception:
        return 0

    return 0


def parse_raw_data(text):
    cleaned = [line.strip() for line in text.strip().splitlines() if line.strip()]
    parsed = []
    i = 0

    while i < len(cleaned):
        try:
            company = cleaned[i]
            rating_line = cleaned[i + 1]

            if "(" in rating_line:
                rating = rating_line.split("(")[0].strip()
                purchase_rating = rating_line.split("(")[1].split("when")[0].strip()
            else:
                rating = rating_line.strip()
                purchase_rating = rating_line.strip()

            interest_amount = cleaned[i + 2]
            callable_line = cleaned[i + 3]

            interest = float(interest_amount.split("%")[0].strip())
            amount = float(interest_amount.split("$")[1].replace(",", "").strip())
            callable_days = parse_callable(callable_line)

            default_rate = default_rates.get(rating, 0)
            recovery_rate = recovery_rates.get(purchase_rating, 0)
            recovery_value = amount * (recovery_rate / 100)

            parsed.append({
                "Company": company,
                "Rating": rating,
                "Rating at Purchase": purchase_rating,
                "Interest Rate": interest,
                "Amount": amount,
                "Callable (Days)": callable_days,
                "Default Rate %": default_rate,
                "Recovery rate %": recovery_rate,
                "Recovery Value ($)": recovery_value
            })

            i += 4

        except Exception:
            i += 1

    return parsed


def cell_value(row, col):
    val = row[col]

    if col == "Amount":
        return money(val)

    if col == "Recovery Value ($)":
        return money(val)

    if col in {"Interest Rate", "Default Rate %", "Recovery rate %"}:
        return pct(val)

    return str(val)


def render_headers():
    head = document.getElementById("table-head")
    head.innerHTML = ""

    for col in columns:
        th = document.createElement("th")
        th.innerText = col

        def make_sort(c):
            def sorter(event):
                sort_table(c)
            return sorter

        th.addEventListener("click", create_proxy(make_sort(col)))
        head.appendChild(th)


def render_table():
    body = document.getElementById("table-body")
    body.innerHTML = ""

    for row in rows:
        tr = document.createElement("tr")

        for col in columns:
            td = document.createElement("td")
            td.innerText = cell_value(row, col)
            tr.appendChild(td)

        body.appendChild(tr)

    update_summary()


def sort_table(col):
    reverse = sort_reverse.get(col, False)

    def sort_key(row):
        if col in {"Rating", "Rating at Purchase"}:
            return rating_order.get(row[col], 0)

        if col in numeric_columns:
            return float(row[col])

        return str(row[col]).lower()

    rows.sort(key=sort_key, reverse=reverse)
    sort_reverse[col] = not reverse
    render_table()


def update_summary():
    total = sum(r["Amount"] for r in rows)
    callable_amt = sum(r["Amount"] for r in rows if r["Callable (Days)"] <= 0)
    recovery = sum(r["Recovery Value ($)"] for r in rows)
    count = len(rows)
    avg = total / count if count else 0

    weighted_risk = sum(
        (r["Default Rate %"] / 100) * (r["Amount"] - r["Recovery Value ($)"])
        for r in rows
    )

    risk_pct = (weighted_risk / total * 100) if total else 0

    document.getElementById("kpi-total").innerText = money(total)
    document.getElementById("kpi-callable").innerText = money(callable_amt)
    document.getElementById("kpi-recovery").innerText = money(recovery)
    document.getElementById("kpi-risk").innerText = f"{money(weighted_risk)} ({risk_pct:.2f}%)"
    document.getElementById("kpi-average").innerText = money(avg)
    document.getElementById("kpi-count").innerText = f"{count:,}"

    render_buckets()


def render_buckets():
    bucket_labels = [
        ("Day 0", lambda r: r["Callable (Days)"] <= 0),
        ("Day 1", lambda r: r["Callable (Days)"] == 1),
        ("Day 2", lambda r: r["Callable (Days)"] == 2),
        ("Day 3", lambda r: r["Callable (Days)"] == 3),
        ("Day 4", lambda r: r["Callable (Days)"] == 4),
        ("Day 5", lambda r: r["Callable (Days)"] == 5),
        ("Day 6", lambda r: r["Callable (Days)"] == 6),
        ("~ 7 Days", lambda r: r["Callable (Days)"] == 7),
        ("After 1 Week", lambda r: r["Callable (Days)"] > 7),
    ]

    container = document.getElementById("bucket-row")
    container.innerHTML = ""

    for label, test in bucket_labels:
        amount = sum(r["Amount"] for r in rows if test(r))

        div = document.createElement("div")
        div.innerHTML = f"""
            <div class="bucket-title">{label}</div>
            <div class="bucket-value">{money(amount)}</div>
        """
        container.appendChild(div)


def save_and_load(event=None):
    global rows

    text = document.getElementById("raw-data").value.strip()

    if not text:
        alert("No data pasted.")
        return

    localStorage.setItem("bond_dashboard_raw_data", text)
    rows = parse_raw_data(text)
    render_table()

    document.getElementById("paste-panel").style.display = "none"


def load_saved(event=None):
    global rows

    saved = localStorage.getItem("bond_dashboard_raw_data")

    if not saved:
        alert("No saved data found.")
        return

    document.getElementById("raw-data").value = saved
    rows = parse_raw_data(saved)
    render_table()


def clear_data(event=None):
    global rows

    localStorage.removeItem("bond_dashboard_raw_data")
    rows = []
    document.getElementById("raw-data").value = ""
    render_table()


def toggle_paste(event=None):
    panel = document.getElementById("paste-panel")

    if panel.style.display == "none" or panel.style.display == "":
        panel.style.display = "block"
    else:
        panel.style.display = "none"


def bind_events():
    document.getElementById("toggle-paste").addEventListener("click", create_proxy(toggle_paste))
    document.getElementById("save-load").addEventListener("click", create_proxy(save_and_load))
    document.getElementById("load-saved").addEventListener("click", create_proxy(load_saved))
    document.getElementById("clear-data").addEventListener("click", create_proxy(clear_data))


render_headers()
render_table()
bind_events()
load_saved()
