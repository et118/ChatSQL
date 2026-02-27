from flask import Flask, redirect, session, render_template, request
from flask_restx import Api

app = Flask(__name__, static_url_path="", static_folder="./static")
# Temporary secret key for development
app.secret_key = b'baba'
app.config["RESTX_MASK_SWAGGER"] = False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session['username'] = request.form['username']
        return redirect("/")
    session['username'] = 'TestUsername'
    return 'Logged in as ' + session['username']

if __name__ == "__main__": #Only gets run when manually running the python file outside the container
    app.run(debug=True)
