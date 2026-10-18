import os
import sqlite3
from flask import Flask, render_template, session, redirect, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import ast
import math

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

MAX_NUMBER = 1000000000000000

@app.route("/")
def index():
    user_id = signed_in()
    if not user_id:
        return redirect("/login")
    history_status = "empty"
    db = open_db()
    history_table = db.execute("SELECT id, row_name, time, expression, result FROM history WHERE user_id = ? ORDER BY time DESC", (user_id,)).fetchall()
    db.close()
    rows = []
    for row in history_table:
        time = datetime.strptime(str(row[2]), "%Y-%m-%d %H:%M:%S")
        time = time.strftime("%d %b %Y, %I:%M %p")
        expression = update_syntax(row[3])
        expression = convert_to_list(expression)
        rows.append((row[0], row[1], time, expression, row[4]))
    if rows:
        history_status = "not_empty"
    return render_template("calc.html", history=rows, history_status=history_status)

@app.route("/login", methods=["GET", "POST"])
def login():
    user_id = signed_in()
    if user_id:
        return redirect("/")
    if request.method == "GET":
        return render_template("login.html")
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username:
            flash("You must type a username")
            return redirect("/login")
        if not password:
            flash("You must type a password")
            return redirect("/login")
        db = open_db()
        user_exists = db.execute("SELECT id, password from users WHERE username = ?", (username,)).fetchall()
        db.close()
        if user_exists:
            hashed_password = user_exists[0][1]
            if check_password_hash(hashed_password, password):
                user_id = user_exists[0][0]
                session["user_id"] = user_id
                return redirect("/")
        flash("Invalid username or password.")
        return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    user_id = signed_in()
    if not user_id:
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")
            if not username:
                flash("You must type a username")
                return redirect("/register")
            if not password:
                flash("You must type a password")
                return redirect("/register")
            db = open_db()
            register_user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchall()
            if not register_user:
                hash_password = generate_password_hash(password)
                db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hash_password))
                db.commit()
                user_info = (db.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, hash_password)).fetchall())
                db.close()
                user_id = user_info[0][0]
                session["user_id"] = user_id
                return redirect("/")
            else:
                flash("You appear to already have an account. Try signing in instead.")
                db.close()
                return redirect("/register")
        elif request.method == "GET":
            return render_template("register.html")
    return redirect("/")

@app.route("/logout", methods= ["GET"])
def logout():
    user_id = signed_in()
    if user_id:
        session.clear()
    return redirect("/login")

def open_db():
    return sqlite3.connect("calc.db")

def signed_in():
    user_id = session.get("user_id")
    return user_id


@app.route("/submit_calculation", methods = ["POST"])
def submit_calculation():
    user_id = signed_in()
    if not user_id:
        return redirect("/login")
    expression = request.form.get("calc_display", "")
    expression = convert_to_string(expression)
    if errors(expression) == False:
        expression = update_syntax(expression)
        calculated = calculate(expression)
        if calculated:
            expression = calculated[0]
            result = calculated[1]
            db = open_db()
            db.execute("INSERT INTO history (user_id, expression, result, time) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", (user_id, expression, result))
            db.commit()
            db.close()
    return redirect("/")

@app.route("/update_expression", methods = ["POST"])
def update_expression():
    user_id = signed_in()
    if not user_id:
        return redirect("/login")
    row_id = request.form.get("row_id")
    expression = request.form.getlist("expression_input")
    expression = convert_to_string(expression)
    if errors(expression) == False:
        expression = update_syntax(expression)
        calculated = calculate(expression)
        if calculated:
            expression = calculated[0]
            result = calculated[1]
            db = open_db()
            db.execute("UPDATE history SET expression = ?, result = ? WHERE id = ? AND user_id = ?", (expression, result, row_id, user_id))
            db.commit()
            db.close()
    return redirect("/")

@app.route("/delete_row", methods = ["POST"])
def delete_row():
    user_id = signed_in()
    if not user_id:
        return redirect("/login")
    row_id = request.form.get("row_id")
    db = open_db()
    db.execute("DELETE FROM history WHERE id = ? AND user_id = ?", (row_id, user_id))
    db.commit()
    db.close()
    return redirect("/")

@app.route("/rename_row", methods= ["POST"])
def rename_row():
    user_id = signed_in()
    if not user_id:
        return redirect("/login")
    if request.method == "POST":
        row_name = request.form.get("rename_input")
        row_id = request.form.get("row_id")
        db = open_db()
        db.execute("UPDATE history SET row_name = ? WHERE id = ? AND user_id = ?", (row_name, row_id, user_id))
        db.commit()
        db.close()
    return redirect("/")

def update_syntax(expression):
    updated_expression = []
    for character in expression:
        if character == "÷":
            updated_expression.append("/")
        elif character in ("\u00D7", "x", "X"):
            updated_expression.append("*")
        else:
            if character != " ":
                updated_expression.append(character)
    return convert_to_string(updated_expression)

def convert_to_string(expression):
    expression_string = ""
    for character in expression:
        expression_string += character
    return expression_string

def convert_to_list(expression):
    expression_list = []
    number = ""
    for i in range(len(expression)):
        if expression[i].isdigit() or expression[i] == ".":
            number += expression[i]
        else:
            if number != "":
                expression_list.append(number)
            expression_list.append(expression[i])
            number = ""
    if number:
        expression_list.append(number)
    return expression_list

# Mathematical functions
def errors(expression):
    if expression == "":
        flash("Nothing was entered into the calculator")
        return True
    elif len(expression) > 100:
        flash("Expression too large. Maximum 100 characters.")
        return True
    for character in expression:
        if character not in ("1234567890+-*/÷\u00D7xX(). "):
            flash("Letters are not allowed (except x for multiplication)")
            return True
    return False

def calculate(expression):
    try:
        tree = ast.parse(expression, mode="eval")
        count = 0
        for node in ast.walk(tree):
            count += 1
        if count > 100:
            raise ValueError("Expression is too long")
        operation = tree.body
        result  = evaluate(operation)
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, RecursionError) as error:
        flash(str(error))
        return None
    return (expression, result)

def evaluate(operation):
    if isinstance(operation, ast.Constant):
        if type(operation.value) not in(int, float):
            raise ValueError("Invalid Number")
        return check_max(operation.value)

    if isinstance(operation, ast.UnaryOp):
        if isinstance(operation.op, ast.USub):
            return check_max(-evaluate(operation.operand))
        elif isinstance(operation.op, ast.UAdd):
            return check_max(evaluate(operation.operand))

    if isinstance(operation, ast.BinOp):
        left = evaluate(operation.left)
        right = evaluate(operation.right)
        if isinstance(operation.op, ast.Add):
            return check_max(left + right)
        elif isinstance(operation.op, ast.Sub):
            return check_max(left - right)
        elif isinstance(operation.op, ast.Mult):
            return check_max(left * right)
        elif isinstance(operation.op, ast.Div):
            return check_max(left / right)
    raise ValueError("Invalid expression")

def check_max(calculation):
    if abs(calculation) > MAX_NUMBER:
        raise ValueError("Result is too large")
    if not math.isfinite(calculation):
        raise ValueError("Invalid numerical result")
    return calculation

