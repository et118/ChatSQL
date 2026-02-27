from flask import Flask, redirect, session, render_template, request
from flask_restx import Api
from time import sleep
import DBManager
import secrets
import re

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


@app.route("/login", methods=["POST"])
def login():
    #Check necessary request data
    if "username" not in request.form or "password" not in request.form:
        return "Missing username or password in request", 400
    
    username = request.form["username"]
    password = request.form["password"]

    #Check if already logged in
    if "auth_token" in session and DBManager.is_auth_token_valid(session["auth_token"], username):
        return redirect("/")

    success, auth_token = DBManager.login(username, password)
    if success:
        session.clear()
        session["auth_token"] = auth_token
        session["username"] = username
        return redirect("/")
    else:
        return "Invalid login credentials. Try another password or username", 401

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
        return "Username too long. Cant be longer than 20 characters", 400
    if len(username) < 5:
        return "Username too short. Cant be shorter than 5 characters", 400
    if not username.isalnum() or not username.isprintable(): #is alphanumeric
        return "Username contains invalid characters", 400

    if len(email) > 254:
        return "Email is too long. Maximum 254 characters", 400
    if not re.fullmatch(email_pattern, email):
        return "Invalid email formatting", 400

    # Just length check, ideally we should check for the complexity as well, but like... no time for that rn
    if len(password) > 128:
        return "Password too long. Cant be longer t han 128 characters", 400
    if len(password) < 8:
        return "Password too short. Cant be shorter than 8 characters", 400
    
    success, auth_token = DBManager.signup(username, email, password)
    if success: #Login automatically if signup successful
        session.clear()
        session["auth_token"] = auth_token
        session["username"] = username
        return redirect("/")
    else:
        return "Username already exists", 400 

if __name__ == "__main__": #Only gets run when manually running the python file outside the container
    app.run(debug=True)
