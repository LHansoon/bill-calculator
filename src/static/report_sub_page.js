
let report_container_element = document.getElementById("email-list-container");
let preset_element = document.getElementById("range-preset");
let range_start_element = document.getElementById("range-start");
let range_end_element = document.getElementById("range-end");

function compute_range() {
    const now = new Date();
    const y = now.getFullYear(), m = now.getMonth();
    switch (preset_element.value) {
        case "this_month":
            return {start: new Date(y, m, 1),
                    end: new Date(y, m + 1, 0, 23, 59, 59)};
        case "last_month":
            return {start: new Date(y, m - 1, 1),
                    end: new Date(y, m, 0, 23, 59, 59)};
        case "this_year":
            return {start: new Date(y, 0, 1),
                    end: new Date(y, 11, 31, 23, 59, 59)};
        case "last_year":
            return {start: new Date(y - 1, 0, 1),
                    end: new Date(y - 1, 11, 31, 23, 59, 59)};
        case "custom": {
            if (!range_start_element.value || !range_end_element.value) {
                return null;   // wait until both dates picked
            }
            let start = new Date(range_start_element.value + "T00:00:00");
            let end = new Date(range_end_element.value + "T23:59:59");
            return {start: start, end: end};
        }
    }
}

function on_range_control_change() {
    const is_custom = preset_element.value === "custom";
    range_start_element.classList.toggle("hidden", !is_custom);
    range_end_element.classList.toggle("hidden", !is_custom);
    refreshModal();
}

preset_element.addEventListener("change", on_range_control_change);
range_start_element.addEventListener("change", on_range_control_change);
range_end_element.addEventListener("change", on_range_control_change);

function openModal() {
    document.getElementById("report-overlay").style.display = "flex";
    append_loader(report_container_element)
    poll_report();
}

function closeModal() {
    document.getElementById("report-overlay").style.display = "none";
    report_container_element.innerHTML = "";
}

function refreshModal(){
    let report_container = document.getElementById("email-list-container");
    report_container.innerHTML = "";
    append_loader(report_container)
    poll_report();
}

function toQueryString(params) {
    return Object.keys(params)
        .map(key => encodeURIComponent(key) + '=' + encodeURIComponent(params[key]))
        .join('&');
}

let translation = {
    "self_purchase": "Pay for self",
    "others_purchase": "Pay for others",
    "total_purchase": "Total pay by user",
    "total_expenditure": "Total spending"
};

function generate_report(report_data) {
    report_container_element.innerHTML = "";
    if (!report_data || Object.keys(report_data).length === 0) {
        report_container_element.innerHTML =
            `<p class="report-empty">No transactions in this range.</p>`;
        return;
    }
    let grand_total = 0;
    let columns = ["self_purchase", "others_purchase", "total_purchase", "total_expenditure"];
    let total_expenditure_index = "total_expenditure";

    for(let user_name in report_data) {
        let user_report_detail = "";
        let user_expenditure_sum = 0;
        let user_section_sum = [];

        for (category in report_data[user_name][total_expenditure_index]){
            user_expenditure_sum += report_data[user_name][total_expenditure_index][category];
        }
        user_expenditure_sum = Math.round(user_expenditure_sum * 100) / 100;
        grand_total += user_expenditure_sum;

        for (let i in columns) {
            let sum_value = 0;
            let user_report_detail_body = "";
            for (let category in report_data[user_name][columns[i]]) {
                let value = report_data[user_name][columns[i]][category];
                user_report_detail_body += `<p> ${category}: ${ value } </p>`;
                sum_value += value;
            }
            sum_value = Math.round(sum_value * 100) / 100;

            let user_report_detail_header = `
                <div class="row-sub-category">
                    <p> ${translation[columns[i]]}: ${sum_value}</p>
                    <hr>
            `;

            user_report_detail += user_report_detail_header;
            user_report_detail += user_report_detail_body;

            user_report_detail += `</div>`;
        }

        report_container_element.innerHTML += `
            <div class="row"  data-user-name="${user_name}">
                <div class="row-main">
                    <span>${user_name}: ${user_expenditure_sum}</span>
                    <button class="expand-report-detail-btn">expand</button>
                </div>
                <div class="row-sub">
                    ${user_report_detail}
                </div>
            </div>
        `;
        //     The following code should be added into div row-main
        //     <input type="email" value="${js_emails[key]}" />
        //     <button>Action</button>
    }

    grand_total = Math.round(grand_total * 100) / 100;
    report_container_element.innerHTML += `
        <div class="row report-grand-total">
            <div class="row-main"><strong>Total: ${grand_total}</strong></div>
        </div>`;
}

function poll_report() {
    const range = compute_range();
    if (range === null) {
        remove_loader(report_container_element);
        return;
    }
    let date_begin = range.start;
    let date_end = range.end;

    let time_params = {
        start_time: date_begin.toISOString(),
        end_time: date_end.toISOString()
    }
    let search_string = toQueryString(time_params);
    fetch(`/get-report?${search_string}`, {method: "GET"})
        .then(response => {
            if (response.status === 200){
                return response.json();
            } else {
                return null
            }
        })
        .then(data => {
            generate_report(data["message"]);
            remove_loader(report_container_element)
            let email_report_btns = document.getElementsByClassName("expand-report-detail-btn");

            for (let i = 0; i < email_report_btns.length; i++) {
                email_report_btns[i].addEventListener("click", function() {
                    let content = this.parentElement.nextElementSibling;

                    if (content.style.display === "flex") {
                        content.style.display = "none";
                    } else {
                        content.style.display = "flex";
                    }
                });
            }
        });
}



