function show_login_popup(status_message = "") {
    document.getElementById('login_form').style.visibility='visible';
    document.getElementById('login_form').style.pointerEvents='auto';
    document.getElementById('overlay_blur').style.visibility='visible';
    document.getElementById('overlay_blur').style.pointerEvents='auto';
    document.getElementById('login_status').innerText = status_message;
}

function show_signup_popup(status_message = "") {
    document.getElementById('signup_form').style.visibility='visible';
    document.getElementById('signup_form').style.pointerEvents='auto';
    document.getElementById('overlay_blur').style.visibility='visible';
    document.getElementById('overlay_blur').style.pointerEvents='auto';
    document.getElementById('signup_status').innerText = status_message;
}

function close_popups() {
    document.getElementById('login_form').style.visibility='hidden';
    document.getElementById('login_form').style.pointerEvents='none';
    document.getElementById('signup_form').style.visibility='hidden';
    document.getElementById('signup_form').style.pointerEvents='none';
    document.getElementById('overlay_blur').style.visibility='hidden';
    document.getElementById('overlay_blur').style.pointerEvents='none';
}

document.addEventListener("DOMContentLoaded", function() {
    const url_params = new URLSearchParams(window.location.search);
    const status_value = url_params.get("s");
    if (!(status_value === null || status_value === "")) {
        let status_message = "";
        switch(status_value) {
            case "0":
                status_message = "Invalid password or username. Please try again";
                break;
            case "1":
                status_message = "Username too long. Can't be longer than 20 characters";
                break;
            case "2":
                status_message = "Username too short. Can't be shorter than 5 characters";
                break;
            case "3":
                status_message = "Username contains invalid characters";
                break;
            case "4":
                status_message = "Email is too long. Can't be longer than 254 characters";
                break;
            case "5":
                status_message = "Invalid email formatting";
                break;
            case "6":
                status_message = "Password too long. Can't be longer than 128 characters";
                break;
            case "7":
                status_message = "Password too short. Can't be shorter than 8 characters";
                break;
            case "8":
                status_message = "Username already exists. Please use another username";
                break;
        }
        if(status_value == "0") {
            show_login_popup(status_message);
        } else {
            show_signup_popup(status_message);
        }
        url_params.delete("s");
        const url = new URL(window.location.href);
        url.search = url_params.toString();
        window.history.replaceState({}, "", url);
    }
});

async function fetch_chats() {
    await fetch("/chats", {
    method: "GET",
    headers: {"Content-Type": "application/json"}
    }).then(response => response.json())
    .then(chats => {
        chats.forEach(chat => {
        let main_div = document.getElementById("chat_history");
        let chat_elem = document.createElement("div");
        chat_elem.classList.add("chat");
        chat_elem.innerText = "Chat: " + chat;
        main_div.appendChild(chat_elem);

        chat_elem.onclick = async() => {
            await fetch("/history", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({chat_id: chat})
            }).then(response => response.json())
            .then(messages => {
                console.log(messages);
                let div = document.getElementById("messages");
                div.replaceChildren();
                messages.forEach(message => {
                    let message_div = document.createElement("div");
                    if(message[0] == 1) {
                        message_div.classList.add("message","bot");
                    } else {
                        message_div.classList.add("message","user");
                    }
                    document.getElementById("messages").appendChild(message_div);
                    let message_p = document.createElement("p");
                    message_p.innerHTML = message[1];
                    message_div.appendChild(message_p);
                });
            });
        }
        });    
    });
}
let is_query_running = false;
let current_result = "";
function start_query() { //Not nicely done. Probably a lot of security vulnerabilities :(
    if(is_query_running) return;
    let query = document.getElementById('query');
    if(query.value == "") return;
    is_query_running = true;
    current_result = "";

    let user_message_div = document.createElement("div");
    user_message_div.classList.add("message","user");
    document.getElementById("messages").appendChild(user_message_div);
    let user_message = document.createElement("p");
    user_message.innerText = query.value;
    user_message_div.appendChild(user_message);

    let bot_message_div = document.createElement("div");
    bot_message_div.classList.add("message","bot");
    document.getElementById("messages").appendChild(bot_message_div);
    let bot_message = document.createElement("p");
    bot_message_div.appendChild(bot_message);

    
    const source = new EventSource("/query?q=" + encodeURIComponent(query.value));
    query.value = "";
    source.onmessage = (event) => {
        if(event.data === "[DONE]") {
            source.close();
            is_query_running = false;
        } else {
            current_result += event.data;
            bot_message.innerHTML += event.data;
            document.getElementById("messages").scrollTo({top: document.getElementById("messages").scrollHeight, behavior: 'smooth'})
        }
    }
}
