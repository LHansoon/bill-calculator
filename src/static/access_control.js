function openAccessModal() {
    document.getElementById("access-overlay").style.display = "flex";
    refresh_key_list();
}

function closeAccessModal() {
    document.getElementById("access-overlay").style.display = "none";
    let box = document.getElementById("key-new-url");
    box.classList.add("hidden");
    box.value = "";
}

function flash_key_url(url) {
    let box = document.getElementById("key-new-url");
    box.classList.remove("hidden");
    box.value = url;
    box.focus();
    box.select();
}

function copy_key_url(url) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url);
    } else {
        // fallback: select the readonly input and copy from it
        flash_key_url(url);
        document.execCommand("copy");
    }
}

function render_key_list(keys) {
    let list = document.getElementById("key-list");
    list.innerHTML = "";
    for (let i = 0; i < keys.length; i++) {
        let entry = keys[i];
        let row = document.createElement("div");
        row.className = "key-row" + (entry["revoked"] ? " key-revoked" : "");

        let label = document.createElement("span");
        label.className = "key-label";
        label.textContent = `${entry["name"]} — created ${entry["created"]}`;
        row.appendChild(label);

        if (entry["revoked"]) {
            let tag = document.createElement("span");
            tag.textContent = "REVOKED";
            row.appendChild(tag);
        } else {
            let copy_btn = document.createElement("button");
            copy_btn.textContent = "Copy";
            copy_btn.onclick = function () { copy_key_url(entry["url"]); };
            row.appendChild(copy_btn);

            let revoke_btn = document.createElement("button");
            revoke_btn.textContent = "Revoke";
            revoke_btn.onclick = function () {
                key_action("revoke", entry["key"], "Revoke this link?");
            };
            row.appendChild(revoke_btn);
        }

        let delete_btn = document.createElement("button");
        delete_btn.textContent = "Delete";
        delete_btn.onclick = function () {
            key_action("delete", entry["key"],
                "Delete this key permanently? The link stops working " +
                "and the row disappears from this list.");
        };
        row.appendChild(delete_btn);

        list.appendChild(row);
    }
}

function refresh_key_list() {
    let xhr = new XMLHttpRequest();
    xhr.open('GET', '/admin/keys');
    xhr.send();
    xhr.onreadystatechange = function () {
        if (this.readyState === 4) {
            if (this.status === 200) {
                render_key_list(JSON.parse(this.responseText)["keys"]);
            } else {
                alert(`请求失败了，code=${this.status}, message=${this.statusText}`);
            }
        }
    }
}

function key_action(action, key, confirm_msg) {
    if (!confirm(confirm_msg)) {
        return;
    }
    let xhr = new XMLHttpRequest();
    xhr.open('POST', `/admin/keys/${action}`);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify({"key": key}));
    xhr.onreadystatechange = function () {
        if (this.readyState === 4) {
            if (this.status === 200) {
                refresh_key_list();
            } else {
                alert(`请求失败了，code=${this.status}, message=${this.statusText}`);
            }
        }
    }
}

let key_create_form = document.getElementById("key-create-form");
key_create_form.onsubmit = function (event) {
    event.preventDefault();

    let name_box = document.getElementById("key-name");
    let name = name_box.value.trim();
    if (name === "") {
        alert("name is empty");
        return;
    }

    let xhr = new XMLHttpRequest();
    xhr.open('POST', '/admin/keys');
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.send(JSON.stringify({"name": name}));
    xhr.onreadystatechange = function () {
        if (this.readyState === 4) {
            if (this.status === 200) {
                name_box.value = "";
                // flash the new link in a copyable readonly input
                flash_key_url(JSON.parse(this.responseText)["url"]);
                refresh_key_list();
            } else {
                alert(`请求失败了，code=${this.status}, message=${this.statusText}`);
            }
        }
    }
}
