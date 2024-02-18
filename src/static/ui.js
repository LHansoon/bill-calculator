// {#code from: https://www.w3schools.com/howto/howto_js_collapsible.asp#}
let coll = document.getElementsByClassName("collapsible");
for (let i = 0; i < coll.length; i++) {
    coll[i].addEventListener("click", function() {
        this.classList.toggle("active");
        let content = this.nextElementSibling;
        if (content.id === "summary-section") {
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


function append_loader(element) {
    const loader = document.createElement("div")
    loader.setAttribute("class", "loader")
    let parent = element.parentElement;
    parent.insertBefore(loader, element.nextSibling);
}

function remove_loader(element) {
    let loaders = element.parentElement.getElementsByClassName("loader");
    for (let i = 0; i < loaders.length; i++){
        loaders[i].remove();
    }
}


function populate_content(result) {
    document.getElementById("major-content").innerHTML = "<h2>现在呢就是这么个状况：</h2>";
    for (let user in result) {
        console.log(user);
        let sub_users = ""
        for (let sub_user in result[user]){
            let btn = `
                <button class="clear_debt_btn" data-from="${user}" data-to="${sub_user}" data-amount="${result[user][sub_user]}" onclick="clearDebt(this)">还钱</button>
            `;

            let sub_user_amount = result[user][sub_user];
            sub_users += `
                <a class="draggable" draggable="true" data-user="${sub_user}" data-amount="${sub_user_amount}">"${sub_user}": ${sub_user_amount} ${btn}</a>
            `;
        }


        let user_entry = `
            <div class="user_entry_container dropzone" data-user="${user}">
                ${user} : { 
                <div class="sub_user_entry_container">
                    ${sub_users}
                </div> }
            </div>
        `.trim();

        document.getElementById("major-content").innerHTML += user_entry;
    }
    load_listeners(result)
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
    const draggable_placeholder = document.createElement("a")
    draggable_placeholder.setAttribute("class", "placeholder")
    draggable_placeholder.innerText = "here"

    let curr_been_dragged = null;
    let curr_been_dragged_parent = null;
    let draggable = document.getElementsByClassName("draggable");
    for (let i = 0; i < draggable.length; i++) {
        draggable[i].addEventListener("dragstart", (event) => {
            curr_been_dragged = event.target;
            curr_been_dragged_parent = event.target.parentElement.parentElement;
        });
    }

    let dropzones = document.getElementsByClassName("dropzone");
    for (let i = 0; i < dropzones.length; i++) {
        dropzones[i].addEventListener("dragenter", (event) => {
            event.preventDefault();
            if (event.target.classList.contains("dropzone")) {
                event.target.querySelector(".sub_user_entry_container").appendChild(draggable_placeholder);
            }
        });
        dropzones[i].addEventListener("dragleave", (event) => {
            if (event.target.classList.contains("dropzone")) {
                try{
                    event.target.querySelector(".sub_user_entry_container").removeChild(draggable_placeholder);
                }
                catch (e) {
                    //pass
                }

            }
        });
        dropzones[i].addEventListener("dragover", (event) => {
            event.preventDefault();

        });
        dropzones[i].addEventListener("drop", (event) => {
            event.preventDefault();
            console.log("2")
            if (event.target.classList.contains("dropzone")) {
                let target_from = event.target.getAttribute("data-user");
                let target_to = curr_been_dragged.getAttribute("data-user");
                let amount = Number(curr_been_dragged.getAttribute("data-amount"));
                let source_from = curr_been_dragged_parent.getAttribute("data-user");
                let source_to = target_to;

                if (source_to === target_from) {
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
                    console.log(js_value);
                }
                populate_content(js_value);
            }
        });
    }
}


populate_content(js_value);