from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from database import create_tables

app = Flask(__name__)
app.secret_key = "exam-portal-demo-key"

create_tables()


def get_db_connection():
    conn = sqlite3.connect("exam_portal.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login-page")
def login_page():
    return render_template("index.html")


@app.route("/login", methods=["POST"])
def login():
    student_name = request.form.get("student_name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not student_name or not email or not password:
        return "Please enter all details!"

    conn = get_db_connection()

    try:
        student = conn.execute(
            "SELECT * FROM students WHERE email = ?",
            (email,)
        ).fetchone()

        if student:
            stored_password = student["password"]

            try:
                password_valid = check_password_hash(
                    stored_password, password
                )
            except (ValueError, TypeError):
                password_valid = False

            # Allow older accounts that stored plain-text passwords
            if not password_valid and stored_password == password:
                password_valid = True

            if not password_valid:
                return "Incorrect password. Please try again."

            session["student_name"] = student["student_name"]
            session["email"] = student["email"]
            return redirect("/exam")

        password_hash = generate_password_hash(password)

        conn.execute(
            """
            INSERT INTO students (student_name, email, password)
            VALUES (?, ?, ?)
            """,
            (student_name, email, password_hash)
        )
        conn.commit()

        session["student_name"] = student_name
        session["email"] = email
        return redirect("/exam")

    except sqlite3.Error:
        return "Database error. Please check the database setup."

    finally:
        conn.close()


@app.route("/exam", methods=["GET", "POST"])
def exam():
    if "student_name" not in session:
        return redirect("/login-page")

    questions = [
        {
            "id": 1,
            "question": "What does HTML stand for?",
            "option_a": "Hyper Text Markup Language",
            "option_b": "High Text Machine Language",
            "option_c": "Home Tool Markup Language",
            "option_d": "Hyperlinks Text Mark Language",
            "answer": "A"
        },
        {
            "id": 2,
            "question": "Which language is used for styling web pages?",
            "option_a": "Python",
            "option_b": "CSS",
            "option_c": "Java",
            "option_d": "C",
            "answer": "B"
        },
        {
            "id": 3,
            "question": "Which tag is used for a paragraph in HTML?",
            "option_a": "<h1>",
            "option_b": "<div>",
            "option_c": "<p>",
            "option_d": "<br>",
            "answer": "C"
        }
    ]

    if request.method == "POST":
        marks = 0

        for q in questions:
            if request.form.get(str(q["id"])) == q["answer"]:
                marks += 1

        total_marks = len(questions)
        percentage = round((marks / total_marks) * 100, 2)
        status = "Pass" if percentage >= 50 else "Fail"

        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO exam_results
                (student_name, subject, marks, total_marks,
                 percentage, status, exam_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["student_name"],
                    "Web Technology",
                    marks,
                    total_marks,
                    percentage,
                    status,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            conn.commit()
        finally:
            conn.close()

        return render_template(
            "result.html",
            student_name=session["student_name"],
            marks=marks,
            total_marks=total_marks,
            percentage=percentage
        )

    return render_template(
        "exam.html",
        student_name=session["student_name"],
        questions=questions
    )

@app.route("/save-result", methods=["POST"])
def save_result():
    if "student_name" not in session:
        return {"error": "Please log in first"}, 401

    data = request.get_json(silent=True) or {}

    try:
        marks = int(data.get("marks", 0))
        total_marks = int(data.get("total_marks", 3))
        percentage = float(data.get("percentage", 0))
    except (TypeError, ValueError):
        return {"error": "Invalid result data"}, 400

    if total_marks <= 0 or marks < 0 or marks > total_marks:
        return {"error": "Invalid marks"}, 400

    if percentage < 0 or percentage > 100:
        return {"error": "Invalid percentage"}, 400

    status = "Pass" if percentage >= 50 else "Fail"

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO exam_results
            (student_name, subject, marks, total_marks,
             percentage, status, exam_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["student_name"],
                "Web Technology",
                marks,
                total_marks,
                percentage,
                status,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
    except sqlite3.Error:
        return {"error": "Could not save exam result"}, 500
    finally:
        conn.close()

    return {"message": "Result saved successfully"}


@app.route("/history")
def history():
    if "student_name" not in session:
        return redirect("/login-page")

    conn = get_db_connection()
    try:
        results = conn.execute(
            """
            SELECT * FROM exam_results
            WHERE student_name = ?
            ORDER BY id DESC
            """,
            (session["student_name"],)
        ).fetchall()
    finally:
        conn.close()

    return render_template("history.html", results=results)


@app.route("/dashboard")
def dashboard():
    if "student_name" not in session:
        return redirect("/login-page")

    conn = get_db_connection()
    try:
        results = conn.execute(
            """
            SELECT * FROM exam_results
            WHERE student_name = ?
            """,
            (session["student_name"],)
        ).fetchall()
    finally:
        conn.close()

    total_exams = len(results)
    pass_count = sum(1 for result in results if result["status"] == "Pass")
    fail_count = sum(1 for result in results if result["status"] == "Fail")

    average_percentage = (
        round(
            sum(result["percentage"] for result in results) / total_exams,
            2
        )
        if total_exams else 0
    )

    return render_template(
        "dashboard.html",
        student_name=session["student_name"],
        total_exams=total_exams,
        average_percentage=average_percentage,
        pass_count=pass_count,
        fail_count=fail_count
    )


@app.route("/logout", methods=["GET"])
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":

    app.run(debug=True)