from flask import Flask
from flask_restx import Api

app = Flask(__name__, static_url_path="", static_folder="./static")
app.config["RESTX_MASK_SWAGGER"] = False

@app.route("/")
def main():
    return app.send_static_file("index.html")

if __name__ == "__main__": #Only gets run when manually running the python file outside the container
    app.run(debug=True)
