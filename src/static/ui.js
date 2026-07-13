// {#code from: https://www.w3schools.com/howto/howto_js_collapsible.asp#}
let coll = document.getElementsByClassName("collapsible");
for (let i = 0; i < coll.length; i++) {
    coll[i].addEventListener("click", function() {
        if (this.classList.contains("summary-btn")){
            this.classList.toggle("active");
        }

        let content = this.nextElementSibling;
        if (content.classList.contains("collapsible-container")) {
            if (content.style.display === "flex") {
                content.style.display = "none";
            } else {
                content.style.display = "flex";
            }
        } else {
            if (content.style.display === "block") {
                content.style.display = "none";
            } else {
                content.style.display = "block";
            }
         }
    });
}

// append spinning loading circle
function append_loader(element) {
    const loader = document.createElement("div")
    loader.setAttribute("class", "loader")
    let parent = element.parentElement;
    parent.insertBefore(loader, element.nextSibling);
}


// the right side warning text after payment
function append_pay_warning(element) {
    let warning = document.getElementById("pay_warning");
    if(warning === null){
        warning = document.createElement("a");
        warning.setAttribute("id", "pay_warning");
        warning.textContent = "success🏅, please note no update on display.";
        warning.style.color = '#' + Math.floor(Math.random() * 16777215).toString(16);

        let parent = element.parentElement;
        parent.insertBefore(warning, element.nextSibling);
    } else {
        warning.style.color = '#' + Math.floor(Math.random() * 16777215).toString(16);
    }

}

function remove_loader(element) {
    let loaders = element.parentElement.getElementsByClassName("loader");
    for (let i = 0; i < loaders.length; i++){
        loaders[i].remove();
    }
}


function populate_content(result) {
    let transfer_count = 0;
    for (let user in result) {
        transfer_count += Object.keys(result[user]).length;
    }

    let html = `<p class="board-hint">${transfer_count} transfer(s) needed to settle up</p>`;

    for (let user in result) {
        let sub_users = "";
        for (let sub_user in result[user]) {
            let sub_user_amount = Number(result[user][sub_user]).toFixed(2);
            sub_users += `
                <a class="draggable pill" draggable="true"
                   data-user="${sub_user}" data-amount="${sub_user_amount}">
                    <span>${sub_user} · $${sub_user_amount}</span>
                    <button class="clear_debt_btn" data-from="${user}"
                            data-to="${sub_user}" data-amount="${sub_user_amount}"
                            onclick="clearDebt(this)">还钱</button>
                </a>`;
        }
        html += `
            <div class="user_entry_container dropzone" data-user="${user}">
                <strong>${user}</strong> owes:
                <div class="sub_user_entry_container">
                    ${sub_users}
                </div>
            </div>`;
    }
    document.getElementById("major-content").innerHTML = html;
    load_listeners(result);
}


function add_user(event, form) {
    event.preventDefault();
    let user_name = form.name.value.trim();
    if (js_value[user_name] != null){
        alert(`user "${user_name}" already exist`);
    } else {
        js_value[user_name] = {};
        populate_content(js_value);
    }
    form.reset();
}


function safe_add(js_value, from, to, amount) {
    if (js_value[from] != null){
        if (js_value[from][to] != null){
            js_value[from][to] += amount;
        } else {
            js_value[from][to] = amount;
        }

        if (js_value[from][to] === 0){
            delete js_value[from][to];
        }
    } else {
        js_value[from] = {};
        safe_add(js_value, from, to, amount);
    }
}


function load_listeners(js_value) {
    let curr_been_dragged = null;
    let curr_been_dragged_parent = null;
    let dropzones = document.getElementsByClassName("dropzone");

    function reset_drag_state() {
        curr_been_dragged = null;
        curr_been_dragged_parent = null;
        for (let i = 0; i < dropzones.length; i++) {
            dropzones[i].classList.remove("drag-over", "drag-source");
        }
    }

    let draggable = document.getElementsByClassName("draggable");
    for (let i = 0; i < draggable.length; i++) {
        draggable[i].addEventListener("dragstart", (event) => {
            curr_been_dragged = event.currentTarget;
            curr_been_dragged_parent = event.currentTarget.closest(".user_entry_container");
            curr_been_dragged_parent.classList.add("drag-source");
            event.dataTransfer.effectAllowed = "move";
        });
        draggable[i].addEventListener("dragend", reset_drag_state);
    }

    for (let i = 0; i < dropzones.length; i++) {
        const zone = dropzones[i];
        // dragenter/dragleave fire on every child boundary; only the
        // outermost pair may toggle the highlight
        let drag_depth = 0;
        zone.addEventListener("dragenter", (event) => {
            event.preventDefault();
            drag_depth++;
            if (drag_depth === 1 && zone !== curr_been_dragged_parent) {
                zone.classList.add("drag-over");
            }
        });
        zone.addEventListener("dragleave", () => {
            drag_depth--;
            if (drag_depth === 0) {
                zone.classList.remove("drag-over");
            }
        });
        zone.addEventListener("dragover", (event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
        });
        zone.addEventListener("drop", (event) => {
            event.preventDefault();
            drag_depth = 0;
            if (curr_been_dragged === null) {
                return;
            }
            let target_from = zone.getAttribute("data-user");
            let target_to = curr_been_dragged.getAttribute("data-user");
            let amount = Number(curr_been_dragged.getAttribute("data-amount"));
            let source_from = curr_been_dragged_parent.getAttribute("data-user");
            let source_to = target_to;
            reset_drag_state();

            if (source_to === target_from || source_from === target_from) {
                alert("你想干嘛");
            } else {
                if (js_value[target_from][source_to] != null) {
                    safe_add(js_value, target_from, source_to, amount);
                    safe_add(js_value, source_from, target_from, amount);
                }else if (js_value[target_from][source_from] != null) {
                    if (js_value[target_from][source_from] < amount) {
                        safe_add(js_value, target_from, source_to, amount);
                        safe_add(js_value, source_from, target_from, amount - js_value[target_from][source_from]);
                        delete js_value[target_from][source_from];
                    } else {
                        safe_add(js_value, target_from, source_from, -amount);
                        safe_add(js_value, target_from, source_to, amount);
                        delete js_value[source_from][source_to];
                    }
                } else {
                    safe_add(js_value, target_from, target_to, amount);
                    safe_add(js_value, source_from, target_from, amount);
                }

                delete js_value[source_from][source_to];
            }
            populate_content(js_value);
        });
    }
}


populate_content(js_value);