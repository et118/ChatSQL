from flask import Flask, redirect, session, render_template, request
from flask_restx import Api
from time import sleep
import DBManager
import secrets
import re

#TODO make sure session cookies get cleared automatically periodically when they expire

DBManager.block_until_connected()
DBManager.rebuild_if_not_initialized() #initialize all new data and setup tables if we are in a new setup

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
    return render_template("index.html")

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

if __name__ == "__main__": #Only gets run when manually running the python file outside the container
    app.run(debug=True)
