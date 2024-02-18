// {#code from: https://www.w3schools.com/howto/howto_js_collapsible.asp#}
let coll = document.getElementsByClassName("collapsible");
let i;
for (i = 0; i < coll.length; i++) {
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

function populate_content(result) {
    for (let user in result) {
        let user_entry = `
            <div class="user_entry_line">
                ${user} : {        
        `.trim();



        console.log(user);
        for (let sub_user in result[user]){
            btn = `
                <button class="clear_debt_btn" data-from="${user}" data-to="${sub_user}" data-amount="${result[user][sub_user]}" onclick="clearDebt(this)">还钱</button>
            `;

            user_entry += `
                <a>"${sub_user}": ${result[user][sub_user]} ${btn}</a>
            `;
        }

        user_entry += `
                }
            </div>
        `.trim();

        document.getElementById("major-content").innerHTML += user_entry;
    }

}

populate_content(js_value);