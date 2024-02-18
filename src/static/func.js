function objectifyForm(formArray) {
    //serialize data function
    let returnArray = {};
    for (var i = 0; i < formArray.length; i++){
        returnArray[formArray[i]['name']] = formArray[i]['value'];
    }
    return returnArray;
}

function clearDebt(btn) {
    let from = btn.getAttribute("data-from")
    let to = btn.getAttribute("data-to")
    let amount = btn.getAttribute("data-amount")

    let xhr = new XMLHttpRequest();
    xhr.open('POST','/pay')
    xhr.setRequestHeader("Content-Type", "application/json");

    //send the form data
    xhr.send(JSON.stringify({"from": from, "to": to, "amount": amount}));
    xhr.onreadystatechange = function() {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            alert("Finished, page will be reloaded")
            window.location.reload();
        }
    }
}

var form = document.getElementById('pay-form');
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
