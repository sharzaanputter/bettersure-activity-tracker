from flask import Flask, render_template, request, redirect, url_for, Response
import psycopg2
import os
from datetime import datetime
import csv
import io

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id SERIAL PRIMARY KEY,
            athlete TEXT,
            month TEXT,
            week TEXT,
            active_days INTEGER,
            active_minutes INTEGER,
            UNIQUE(athlete, month, week)
        )
    """)
    conn.commit()
    conn.close()
except Exception as e:
    print(f"DB init error: {e}")

athletes = ["Sharzaan", "Aneldi", "Josh", "Tshepo", "Jordaan", "Louise", "Rachel", "Hanli", "Jabu", "Lindile", "Julie", "Seu", "Jeanette", "Gavin", "Gina", "Monique", "Regard", "Marene", "Jeandre", "George", "Maxine", "Tammy", "Alex", "Christo T"]
months = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
weeks = ["Week 1", "Week 2", "Week 3", "Week 4"]

def get_conn():
    return psycopg2.connect(DATABASE_URL)

@app.route("/", methods=["GET"])
def select_athlete():
    return render_template("select.html", athletes=athletes)

@app.route("/home", methods=["GET", "POST"])
def home():
    current_month = datetime.now().strftime("%B")

    if request.method == "POST":
        athlete = request.form["athlete"]
        month = request.form["month"]
        week = request.form["week"]
        active_days = request.form["active_days"] or None
        active_minutes = request.form["active_minutes"] or None

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO entries (athlete, month, week, active_days, active_minutes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(athlete, month, week) DO UPDATE SET
                active_days = EXCLUDED.active_days,
                active_minutes = EXCLUDED.active_minutes
        """, (athlete, month, week, active_days, active_minutes))
        conn.commit()
        conn.close()

        return redirect(url_for("home", athlete=athlete))

    selected_athlete = request.args.get("athlete", "")

    if not selected_athlete or selected_athlete not in athletes:
        return redirect(url_for("select_athlete"))

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT athlete, month, week, active_days, active_minutes FROM entries")
    rows = cursor.fetchall()
    conn.close()

    pivot = {}
    for row in rows:
        athlete, month, week, active_days, active_minutes = row
        key = (athlete, month)
        if key not in pivot:
            pivot[key] = {}
        pivot[key][week] = {"days": active_days, "minutes": active_minutes}

    days_table = []
    minutes_table = []

    for (athlete, month), week_data in pivot.items():
        days_row = {
            "Athlete": athlete,
            "Month": month,
            "Week 1": week_data.get("Week 1", {}).get("days", ""),
            "Week 2": week_data.get("Week 2", {}).get("days", ""),
            "Week 3": week_data.get("Week 3", {}).get("days", ""),
            "Week 4": week_data.get("Week 4", {}).get("days", ""),
            "Total": sum(week_data.get(f"Week {i}", {}).get("days", 0) or 0 for i in range(1, 5))
        }
        days_table.append(days_row)

        minutes_row = {
            "Athlete": athlete,
            "Month": month,
            "Week 1": week_data.get("Week 1", {}).get("minutes", ""),
            "Week 2": week_data.get("Week 2", {}).get("minutes", ""),
            "Week 3": week_data.get("Week 3", {}).get("minutes", ""),
            "Week 4": week_data.get("Week 4", {}).get("minutes", ""),
            "Total": sum(week_data.get(f"Week {i}", {}).get("minutes", 0) or 0 for i in range(1, 5))
        }
        minutes_table.append(minutes_row)

    return render_template("home.html", athletes=athletes, months=months, weeks=weeks,
                           days_table=days_table, minutes_table=minutes_table,
                           current_month=current_month,
                           selected_athlete=selected_athlete)

@app.route("/matrix")
def matrix():
    athlete = request.args.get("athlete", "")
    return render_template("matrix.html", athlete=athlete)

@app.route("/download")
def download():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT athlete, month, week, active_days, active_minutes FROM entries")
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Athlete", "Month", "Week", "Active Days", "Active Minutes"])
    writer.writerows(rows)
    output.seek(0)

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=activity_data.csv"}
    )

@app.route("/pastwinners")
def pastwinners():
    athlete = request.args.get("athlete", "")
    return render_template("pastwinners.html", athlete=athlete)

if __name__ == "__main__":
    app.run(debug=True)