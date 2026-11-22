
let report_container_element = document.getElementById("report-container");
let preset_element = document.getElementById("range-preset");
let range_start_element = document.getElementById("range-start");
let range_end_element = document.getElementById("range-end");
let range_label_element = document.getElementById("range-label");

// only the response to the latest request is rendered
let report_request_id = 0;
// last successful data, kept so sorting the table does not refetch
let report_transactions = [];
let tx_sort = {key: "date", asc: false};


// ---------- dates (always local calendar dates, never UTC) ----------

function fmt_date(d) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function preset_range(preset) {
    const now = new Date();
    const y = now.getFullYear(), m = now.getMonth(), d = now.getDate();
    switch (preset) {
        case "this_week": {
            const offset = (now.getDay() + 6) % 7;   // Monday = 0
            return {start: new Date(y, m, d - offset), end: new Date(y, m, d - offset + 6)};
        }
        case "last_7_days":
            return {start: new Date(y, m, d - 6), end: new Date(y, m, d)};
        case "last_30_days":
            return {start: new Date(y, m, d - 29), end: new Date(y, m, d)};
        case "this_month":
            return {start: new Date(y, m, 1), end: new Date(y, m + 1, 0)};
        case "last_month":
            return {start: new Date(y, m - 1, 1), end: new Date(y, m, 0)};
        case "this_year":
            return {start: new Date(y, 0, 1), end: new Date(y, 11, 31)};
        case "last_year":
            return {start: new Date(y - 1, 0, 1), end: new Date(y - 1, 11, 31)};
    }
    return null;
}

// returns {start, end} as "YYYY-MM-DD" strings, or null while custom is incomplete
function compute_range() {
    const preset = preset_element.value;
    if (preset === "all_time") {
        return {start: "1900-01-01", end: "9999-12-31"};
    }
    if (preset === "custom") {
        if (!range_start_element.value || !range_end_element.value) {
            return null;
        }
        return {start: range_start_element.value, end: range_end_element.value};
    }
    const r = preset_range(preset);
    return {start: fmt_date(r.start), end: fmt_date(r.end)};
}

function update_range_label(range) {
    if (range === null) {
        range_label_element.textContent = "pick both dates";
    } else if (preset_element.value === "all_time") {
        range_label_element.textContent = "";
    } else {
        range_label_element.textContent = `${range.start} ~ ${range.end}`;
    }
}

let last_preset = preset_element.value;
function on_preset_change() {
    const is_custom = preset_element.value === "custom";
    if (is_custom && !range_start_element.value && !range_end_element.value) {
        // start custom from whatever range was showing
        const prev = preset_range(last_preset);
        if (prev !== null) {
            range_start_element.value = fmt_date(prev.start);
            range_end_element.value = fmt_date(prev.end);
        }
    }
    last_preset = preset_element.value;
    range_start_element.classList.toggle("hidden", !is_custom);
    range_end_element.classList.toggle("hidden", !is_custom);
    refreshModal();
}

preset_element.addEventListener("change", on_preset_change);
range_start_element.addEventListener("change", refreshModal);
range_end_element.addEventListener("change", refreshModal);


// ---------- modal ----------

function openModal() {
    document.getElementById("report-overlay").style.display = "flex";
    refreshModal();
}

function closeModal() {
    document.getElementById("report-overlay").style.display = "none";
    report_request_id++;   // drop any response still in flight
    remove_loader(report_container_element);
    report_container_element.innerHTML = "";
}

function refreshModal() {
    report_container_element.innerHTML = "";
    remove_loader(report_container_element);
    poll_report();
}

function toQueryString(params) {
    return Object.keys(params)
        .map(key => encodeURIComponent(key) + '=' + encodeURIComponent(params[key]))
        .join('&');
}

function escape_html(value) {
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function category_label(category) {
    return category === "" ? "(no category)" : category;
}

function money(value) {
    return Number(value).toFixed(2);
}


// ---------- per-user summary ----------

let translation = {
    "self_purchase": "Pay for self",
    "others_purchase": "Pay for others",
    "total_purchase": "Total pay by user",
    "total_expenditure": "Total spending"
};

function summary_html(report_data) {
    let html = "";
    let grand_total = 0;
    let columns = ["self_purchase", "others_purchase", "total_purchase", "total_expenditure"];

    for (let user_name in report_data) {
        let user_expenditure_sum = 0;
        for (let category in report_data[user_name]["total_expenditure"]) {
            user_expenditure_sum += report_data[user_name]["total_expenditure"][category];
        }
        grand_total += user_expenditure_sum;

        let user_report_detail = "";
        for (let column of columns) {
            let sum_value = 0;
            let body = "";
            for (let category in report_data[user_name][column]) {
                let value = report_data[user_name][column][category];
                body += `<p> ${escape_html(category_label(category))}: ${money(value)} </p>`;
                sum_value += value;
            }
            user_report_detail += `
                <div class="row-sub-category">
                    <p> ${translation[column]}: ${money(sum_value)}</p>
                    <hr>
                    ${body}
                </div>`;
        }

        html += `
            <div class="row" data-user-name="${escape_html(user_name)}">
                <div class="row-main">
                    <span>${escape_html(user_name)}: ${money(user_expenditure_sum)}</span>
                    <button class="expand-report-detail-btn">expand</button>
                </div>
                <div class="row-sub">
                    ${user_report_detail}
                </div>
            </div>`;
    }

    html += `
        <div class="row report-grand-total">
            <div class="row-main"><strong>Total: ${money(grand_total)}</strong></div>
        </div>`;
    return html;
}

// one delegated listener instead of re-binding every button on each refresh
report_container_element.addEventListener("click", (event) => {
    const btn = event.target.closest(".expand-report-detail-btn");
    if (btn !== null) {
        const content = btn.parentElement.nextElementSibling;
        const open = content.style.display === "flex";
        content.style.display = open ? "none" : "flex";
        btn.textContent = open ? "expand" : "collapse";
        return;
    }
    const th = event.target.closest("th[data-sort]");
    if (th !== null) {
        const key = th.getAttribute("data-sort");
        if (tx_sort.key === key) {
            tx_sort.asc = !tx_sort.asc;
        } else {
            // dates and amounts read best biggest-first, text A-Z
            tx_sort = {key: key, asc: !(key === "date" || key === "amount")};
        }
        render_transactions();
    }
});


// ---------- transaction table ----------

let tx_columns = [
    {key: "date", label: "Date"},
    {key: "merchant", label: "Merchant"},
    {key: "category", label: "Category"},
    {key: "event_tag", label: "Tag"},
    {key: "paid_by", label: "Paid by"},
    {key: "user", label: "For"},
    {key: "amount", label: "Share", numeric: true},
];

function sorted_transactions() {
    const {key, asc} = tx_sort;
    const dir = asc ? 1 : -1;
    // copy, then stable sort; date as tie-breaker keeps groups readable
    return report_transactions.slice().sort((a, b) => {
        let cmp = key === "amount"
            ? a.amount - b.amount
            : String(a[key]).localeCompare(String(b[key]));
        if (cmp === 0 && key !== "date") {
            cmp = String(b.date).localeCompare(String(a.date)) * dir;
        }
        return cmp * dir;
    });
}

function transactions_html() {
    if (report_transactions.length === 0) {
        return "";
    }
    let head = tx_columns.map(c => {
        const arrow = tx_sort.key === c.key ? (tx_sort.asc ? " ▲" : " ▼") : "";
        const cls = c.numeric ? ' class="num"' : "";
        return `<th data-sort="${c.key}"${cls}>${c.label}${arrow}</th>`;
    }).join("");

    let rows = sorted_transactions().map(t => {
        return "<tr>" + tx_columns.map(c => {
            if (c.key === "amount") {
                return `<td class="num">${money(t.amount)}</td>`;
            }
            let v = c.key === "category" ? category_label(t.category) : t[c.key];
            return `<td>${escape_html(v)}</td>`;
        }).join("") + "</tr>";
    }).join("");

    return `
        <h3>${report_transactions.length} transaction(s)</h3>
        <p class="report-note">One line per person per bill; "Share" is that person's part.</p>
        <table class="report-tx">
            <thead><tr>${head}</tr></thead>
            <tbody>${rows}</tbody>
        </table>`;
}

function render_transactions() {
    const holder = document.getElementById("report-tx-holder");
    if (holder !== null) {
        holder.innerHTML = transactions_html();
    }
}


// ---------- fetch + render ----------

function generate_report(report_data, transactions) {
    report_transactions = transactions || [];
    if (!report_data || Object.keys(report_data).length === 0) {
        report_container_element.innerHTML =
            `<p class="report-empty">No transactions in this range.</p>`;
        return;
    }
    report_container_element.innerHTML =
        summary_html(report_data) + `<div id="report-tx-holder"></div>`;
    render_transactions();
}

function show_report_error(message) {
    report_container_element.innerHTML =
        `<p class="report-error">Failed to load report: ${escape_html(message)}</p>`;
}

function poll_report() {
    const range = compute_range();
    update_range_label(range);
    if (range === null) {
        return;
    }

    const request_id = ++report_request_id;
    append_loader(report_container_element);

    fetch(`/get-report?${toQueryString({start_time: range.start, end_time: range.end})}`)
        .then(response => response.json().then(
            data => ({ok: response.ok, status: response.status, data: data}),
            () => ({ok: false, status: response.status, data: null})))
        .then(({ok, status, data}) => {
            if (request_id !== report_request_id) {
                return;   // a newer request superseded this one
            }
            remove_loader(report_container_element);
            if (!ok || data === null || data["result"] !== true) {
                show_report_error((data && data["message"]) || `HTTP ${status}`);
                return;
            }
            generate_report(data["message"], data["transactions"]);
        })
        .catch(error => {
            if (request_id !== report_request_id) {
                return;
            }
            remove_loader(report_container_element);
            show_report_error(error.message);
        });
}
