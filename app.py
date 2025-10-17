from flask import Flask, render_template, request

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/add", methods=["POST"])
def add():
    number1 = request.form.get("number1")
    number2 = request.form.get("number2")

    ans = int(number1) + int(number2)

    return render_template("result.html", result=ans)

if __name__ == '__main__':
    app.run(debug=True)