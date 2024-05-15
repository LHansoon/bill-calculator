function clearDebt(btn) {
    btn.disabled = true;
    append_loader(btn.parentElement);
    let from = btn.getAttribute("data-from")
    let to = btn.getAttribute("data-to")
    let amount = btn.getAttribute("data-amount")

    let xhr = new XMLHttpRequest();
    xhr.open('POST','/pay')
    xhr.setRequestHeader("Content-Type", "application/json");

    //send the form data
    xhr.send(JSON.stringify({"from": from, "to": to, "amount": amount}));
    xhr.onreadystatechange = function() {
        if (this.readyState === 4) {
            remove_loader(btn.parentElement);
            if (this.status === 200){
                delete js_value[from][to];
                populate_content(js_value);
            } else {
                btn.disabled = false;
                alert(`请求失败了，code=${this.status}, message=${this.statusText}`);
            }
        }
    }
}

let form = document.getElementById('pay-form');
let form_submit_btn = document.getElementById("pay_button")
form_submit_btn.onclick = function(event){
    let xhr = new XMLHttpRequest();
    let formData = new FormData(form);
    let formDataDict = Object.fromEntries(formData);
    let from = formDataDict["from"];
    let to = formDataDict["to"];
    let amount = Number(formDataDict["amount"]);

    if (amount === 0){
        alert("no 0");
        return;
    }

    append_loader(form_submit_btn);

    xhr.open('POST','/pay')

    xhr.setRequestHeader("Content-Type", "application/json");

    //send the form data
    xhr.send(JSON.stringify(Object.fromEntries(formData)));

    xhr.onreadystatechange = function() {
        if (this.readyState === 4) {
            remove_loader(form_submit_btn);
            if (this.status === 200){
                populate_content(js_value);
                form.reset();
                append_pay_warning(form_submit_btn);
            } else {
                form_submit_btn.disabled = false;
                alert(`请求失败了，code=${this.status}, message=${this.statusText}`);
            }
        }
    }
    //Fail the onsubmit to avoid page refresh.
    return false;
}

let add_user_form = document.getElementById("add-user-form");
add_user_form.onsubmit = function (event){
    add_user(event, add_user_form);
}


let chat_form = document.getElementById("chat-post-form");
chat_form.onsubmit = function (event) {
    event.preventDefault();

    let chat_btn = document.getElementById("chat-btn");
    let chat_message_box = document.getElementById("chat-message");
    append_loader(chat_btn);

    chat_btn.disabled = true;
    let xhr = new XMLHttpRequest();
    let formData = new FormData(chat_form);

    xhr.open('POST','/chat-post')
    xhr.setRequestHeader("Content-Type", "application/json");

    //send the form data
    xhr.send(JSON.stringify(Object.fromEntries(formData)));

    xhr.onreadystatechange = function() {
        if (this.readyState === 4) {
            chat_btn.disabled = false;
            remove_loader(chat_btn);
            if (this.status === 200){
                chat_message_box.value = "";
            } else {
                alert(`请求失败了，code=${this.status}, message=${this.responseText}`);
            }
        }
    }
}


function update_chat_box(message) {
    message = JSON.parse(message);
    let chat_box = document.getElementById("chat");
    chat_box.innerHTML = "";
    for (let i = 0; i < message.length; i++){
        let chat_entry = `
            <div class="chat-entry"><a class="chat-ts">${message[i]["ts"]}</a> == <a class="chat-name">${message[i]["name"]}</a>: <a class="chat-message">${message[i]["message"]}</a></div>
        `;
        chat_box.innerHTML += chat_entry;
    }
    chat_box.scrollTop = chat_box.scrollHeight;
}

let cache_json = "";
function poll_content() {
    fetch("/get-chat", {method: "GET"})
        .then(response => {
            if (response.status === 200){
                return response.json();
            } else {
                return null
            }
        })
        .then(data => {
            let response_message = data["message"];
            if (cache_json !== response_message){
                cache_json = response_message;
                update_chat_box(response_message);
            }
        });
}


const pollingInterval = 1000;
const pollTimer = setInterval(() => {
    poll_content();
}, pollingInterval);
poll_content();