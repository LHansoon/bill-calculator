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
form.onsubmit = function(event){
    let xhr = new XMLHttpRequest();
    let formData = new FormData(form);

    xhr.open('POST','/pay')

    xhr.setRequestHeader("Content-Type", "application/json");

    //send the form data
    xhr.send(JSON.stringify(Object.fromEntries(formData)));

    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            alert("Finished, page will be reloaded")
            window.location.reload();
        }
    }
    //Fail the onsubmit to avoid page refresh.
    return false;
}

let add_user_form = document.getElementById("add-user-form");
add_user_form.onsubmit = function (event){
    add_user(event, add_user_form);
}