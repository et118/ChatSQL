from flask import Flask, redirect, session, render_template, request, Response
from flask_restx import Api
from time import sleep
import DBManager
import ChatManager
import secrets
import re

#TODO make sure session cookies get cleared automatically periodically when they expire

DBManager.block_until_connected()
DBManager.rebuild_if_not_initialized() #initialize all new data and setup tables if we are in a new setup
ChatManager.train_if_not_initialized()

app = Flask(__name__, static_url_path="", static_folder="./static")
# Hardcoded and not so secret secret key, since we aren't in production
# This will be used to make sure that the cookies arent able to be 
# read by xss or any other vulnerability. Limiting the vulnerabilities to
# the browser itself, or the users computer.
app.secret_key = b'baba'
# Credits to this really nifty website for this email matching regex: https://emailregex.com/
email_pattern = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"

@app.route("/")
def index():
    #Whenever we load main page, we dont have a chat selected
    session.pop("chat_id", None)
    return render_template("index.html")

@app.route("/stats")
def stats():
    if "auth_token" not in session:
        return "You need to be logged in to view statistics", 400
    return render_template("statistics.html")

@app.route("/words_stats", methods=["GET"])
def words_stats():
    stats = DBManager.get_word_database_stats()
    json = []
    for word, amount in stats:
        json.append([word,amount])
    return json, 200

@app.route("/word_stats", methods=["POST"])
def word_stats():
    stats = DBManager.get_word_stats(request.get_json()["word"])
    json = []
    for keyword, predict_word, count, cumulative_weight, total_weight in stats:
        json.append([keyword, predict_word, count, cumulative_weight, total_weight])
    return json, 200

@app.route("/user_stats", methods=["GET"])
def user_stats():
    users, sessions  = DBManager.get_user_stats()
    json = {"users":[], "sessions":[]}
    for user_id, username, email, password_hash in users:
        json["users"].append([user_id, username, email, password_hash])
    for username, auth_token_hash, expiry_date in sessions:
        json["sessions"].append([username, auth_token_hash, expiry_date])
    return json
    

@app.before_request
def expire_session_check():
    #Check for malformed session cookies. Like only having one of the two
    if ("username" in session and "auth_token" not in session) or \
       ("auth_token" in session and "username" not in session):
        session.clear()
        return
    #Check if auth_token is alive. If not, clear all session cookies. Note: This queries the database for every request to check if token is still alive. Might not be good for production.
    if "auth_token" in session and "username" in session and not DBManager.is_auth_token_valid(session["auth_token"], session["username"]):
        session.clear()
        return

@app.route("/login", methods=["POST"])
def login():
    #Check necessary request data
    if "username" not in request.form or "password" not in request.form:
        return "Missing username or password in request", 400
    
    username = request.form["username"]
    password = request.form["password"]
    
    if len(username) == 0:
        return "You can't use an empty username", 400
    if len(password) == 0:
        return "You can't use an empty password", 400

    #Check if already logged in (safety check incase we try to login while already logged in)
    if "auth_token" in session and DBManager.is_auth_token_valid(session["auth_token"], username):
        return redirect("/")

    success, auth_token = DBManager.login(username, password)
    if success:
        session.clear()
        session["auth_token"] = auth_token
        session["username"] = username
        return redirect("/")
    else:
        return redirect("/?s=0") #Invalid password or username

@app.route("/logout", methods=["POST"])
def logout():
    #For now we just do a simple dirty trick and remove the session cookies
    #TODO remove the current session cookie from the database as well
    DBManager.invalidate_auth_token(session["auth_token"], session["username"])
    session.clear()
    return redirect("/")

@app.route("/signup", methods=["POST"])
def signup():
    #Check necessary request data
    if "username" not in request.form or "email" not in request.form or "password" not in request.form:
        return "Missing username, email or password in request", 400
    
    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]

    #Check requirements for username, email, password
    if len(username) > 20:
        return redirect("/?s=1")#Username too long. Cant be longer than 20 characters
    if len(username) < 5:
        return redirect("/?s=2")#Username too short. Cant be shorter than 5 characters
    if not username.isalnum() or not username.isprintable(): #is alphanumeric
        return redirect("/?s=3")#Username contains invalid characters

    if len(email) > 254:
        return redirect("/?s=4")#Email is too long. Maximum 254 characters
    if not re.fullmatch(email_pattern, email):
        return redirect("/?s=5")#Invalid email formatting

    # Just length check, ideally we should check for the complexity as well, but like... no time for that rn
    if len(password) > 128:
        return redirect("/?s=6")#Password too long. Cant be longer t han 128 characters
    if len(password) < 8:
        return redirect("/?s=7")#Password too short. Cant be shorter than 8 characters

    success, auth_token = DBManager.signup(username, email, password)
    if success: #Login automatically if signup successful
        session.clear()
        session["auth_token"] = auth_token
        session["username"] = username
        return redirect("/")
    else:
        return redirect("/?s=8")#Username already exists


# The streaming done here works, but i wouldn't trust it with multiple users at once. No time for it though. It works for demonstration atleast.
@app.route("/query", methods=["GET"])
def query():
    if "auth_token" not in session or "username" not in session:
        return "Missing auth_token and/or username header", 400
    if not DBManager.is_auth_token_valid(session["auth_token"], session["username"]):
        return "Invalid session", 400

    if "chat_id" not in session:
        session["chat_id"] = DBManager.create_new_chat(session["auth_token"])
    query = request.args.get("q", "")
    DBManager.create_new_message(session["chat_id"], query, session["auth_token"])
    return Response(ChatManager.predict_next_words(query, session["chat_id"]), mimetype="text/event-stream")

@app.route("/chats", methods=["GET"])
def chats():
    if "auth_token" not in session or "username" not in session:
        return "Missing auth_token and/or username header", 400
    if not DBManager.is_auth_token_valid(session["auth_token"], session["username"]):
        return "Invalid session", 400

    chats = DBManager.get_chats(session["auth_token"])
    ret = []
    for chat in chats:
        ret.append(chat[0])
    return ret, 200

@app.route("/history", methods=["POST"])
def history():
    if "auth_token" not in session or "username" not in session:
        return "Missing auth_token and/or username header", 400
    if not DBManager.is_auth_token_valid(session["auth_token"], session["username"]):
        return "Invalid session", 400
    print(request.get_json())
    chat_id = request.get_json()["chat_id"]
    session["chat_id"] = chat_id
    
    messages = DBManager.get_chat_history(session["chat_id"], session["auth_token"])
    return messages, 200

if __name__ == "__main__": #Only gets run when manually running the python file outside the container
    app.run(debug=True, threaded=True, port=5000, host="0.0.0.0")
