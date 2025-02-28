
let report_container_element = document.getElementById("email-list-container");
let year_input_element = document.getElementById("year-input");
let month_input_element = document.getElementById("month-input");

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
}

function poll_report() {
    let date_begin = new Date(year_input_element.value, month_input_element.value - 1, 1);
    let date_end = new Date(year_input_element.value, month_input_element.value - 1, 31, 24, 59, 59);

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



