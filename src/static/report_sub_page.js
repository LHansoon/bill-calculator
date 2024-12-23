
let report_container_element = document.getElementById("email-list-container");
let year_input_element = document.getElementById("year-input");

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

function generate_report(report_data) {
    report_container_element.innerHTML = "";

    for(let user_name in report_data) {
        let user_report_detail = "";

        for (let key2 in report_data[user_name]) {
            user_report_detail += `
                <div class="row-sub-category">
                    <p> ${key2}: </p>
                    <hr>
            `;

            for (let category in report_data[user_name][key2]) {
                user_report_detail += `<p> ${category}: ${report_data[user_name][key2][category]} </p>`;
            }

            user_report_detail += `</div>`;
        }

        report_container_element.innerHTML += `
            <div class="row"  data-user-name="${user_name}">
                <div class="row-main">
                    <span>${user_name}: ${js_total_summary[user_name]}</span>
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
    let year_begin = new Date(year_input_element.value, 0, 1);
    let year_end = new Date(year_input_element.value, 11, 31, 24, 59, 59);

    let time_params = {
        start_time: year_begin.toISOString(),
        end_time: year_end.toISOString()
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



