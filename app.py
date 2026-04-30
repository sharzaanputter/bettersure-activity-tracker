from flask import Flask, render_template, request, redirect, url_for, Response, jsonify
import psycopg2
import os
from datetime import datetime
import csv
import io

app = Flask(__name__)

def check_bingo(completed_cells):
    completed = set(completed_cells) | {12}
    lines = [
        [0,1,2,3,4],[5,6,7,8,9],[10,11,12,13,14],[15,16,17,18,19],[20,21,22,23,24],
        [0,5,10,15,20],[1,6,11,16,21],[2,7,12,17,22],[3,8,13,18,23],[4,9,14,19,24],
        [0,6,12,18,24],[4,8,12,16,20]
    ]
    return any(all(i in completed for i in line) for line in lines)

def init_db():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id SERIAL PRIMARY KEY,
            athlete TEXT, month TEXT, week TEXT,
            active_days INTEGER, active_minutes INTEGER,
            UNIQUE(athlete, month, week)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bingo_cells (
            athlete TEXT,
            week TEXT DEFAULT 'Week 1',
            cell_index INTEGER,
            UNIQUE(athlete, week, cell_index)
        )
    """)
    try:
        cursor.execute("ALTER TABLE bingo_cells ADD COLUMN week TEXT DEFAULT 'Week 1'")
        conn.commit()
    except:
        conn.rollback()
    try:
        cursor.execute("ALTER TABLE bingo_cells ADD CONSTRAINT bingo_uq UNIQUE(athlete, week, cell_index)")
        conn.commit()
    except:
        conn.rollback()
    conn.commit()
    conn.close()

def get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")

athletes = ["Sharzaan", "Aneldi", "Josh", "Tshepo", "Jordaan", "Louise", "Rachel", "Hanli", "Jabu", "Lindile", "Julie", "Seu", "Jeanette", "Gavin", "Gina", "Monique", "Regard", "Marene", "Jeandre", "George", "Maxine", "Tammy", "Alex", "Christo T", "Berget", "Tebogo","Remone","Kea"]
months = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
weeks = ["Week 1", "Week 2", "Week 3", "Week 4"]

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
            "Athlete": athlete, "Month": month,
            "Week 1": week_data.get("Week 1", {}).get("days", ""),
            "Week 2": week_data.get("Week 2", {}).get("days", ""),
            "Week 3": week_data.get("Week 3", {}).get("days", ""),
            "Week 4": week_data.get("Week 4", {}).get("days", ""),
            "Total": sum(week_data.get(f"Week {i}", {}).get("days", 0) or 0 for i in range(1, 5))
        }
        days_table.append(days_row)
        minutes_row = {
            "Athlete": athlete, "Month": month,
            "Week 1": week_data.get("Week 1", {}).get("minutes", ""),
            "Week 2": week_data.get("Week 2", {}).get("minutes", ""),
            "Week 3": week_data.get("Week 3", {}).get("minutes", ""),
            "Week 4": week_data.get("Week 4", {}).get("minutes", ""),
            "Total": sum(week_data.get(f"Week {i}", {}).get("minutes", 0) or 0 for i in range(1, 5))
        }
        minutes_table.append(minutes_row)

    days_table.sort(key=lambda x: x["Total"], reverse=True)
    minutes_table.sort(key=lambda x: x["Total"], reverse=True)

    return render_template("home.html", athletes=athletes, months=months, weeks=weeks,
                           days_table=days_table, minutes_table=minutes_table,
                           current_month=current_month, selected_athlete=selected_athlete)

@app.route("/bingo")
def bingo_summary():
    selected_athlete = request.args.get("athlete", "")
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT athlete, week, cell_index FROM bingo_cells")
    rows = cursor.fetchall()
    conn.close()

    data = {athlete: {week: [] for week in weeks} for athlete in athletes}
    for athlete, week, cell_index in rows:
        if athlete in data and week in data[athlete]:
            data[athlete][week].append(cell_index)

    summary = {}
    for athlete in athletes:
        summary[athlete] = {}
        for week in weeks:
            cells = data[athlete][week]
            count = len(set(cells) - {12})
            summary[athlete][week] = {
                "count": count,
                "bingo": check_bingo(cells)
            }

    return render_template("bingo_summary.html", athletes=athletes, weeks=weeks,
                           summary=summary, selected_athlete=selected_athlete)

@app.route("/matrix")
def matrix():
    athlete = request.args.get("athlete", "")
    week = request.args.get("week", "Week 1")
    if not athlete:
        return redirect(url_for("bingo_summary"))

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT cell_index FROM bingo_cells WHERE athlete = %s AND week = %s",
                   (athlete, week))
    completed = [row[0] for row in cursor.fetchall()]
    conn.close()

    if 12 not in completed:
        completed.append(12)

    return render_template("matrix.html", athlete=athlete, week=week, completed=completed)

@app.route("/matrix/toggle", methods=["POST"])
def toggle_cell():
    data = request.get_json()
    athlete = data.get("athlete")
    week = data.get("week")
    cell_index = data.get("cell_index")

    if cell_index == 12:
        return jsonify({"status": "free"})

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM bingo_cells WHERE athlete = %s AND week = %s AND cell_index = %s",
                   (athlete, week, cell_index))
    exists = cursor.fetchone()

    if exists:
        cursor.execute("DELETE FROM bingo_cells WHERE athlete = %s AND week = %s AND cell_index = %s",
                       (athlete, week, cell_index))
        completed = False
    else:
        cursor.execute("INSERT INTO bingo_cells (athlete, week, cell_index) VALUES (%s, %s, %s)",
                       (athlete, week, cell_index))
        completed = True

    conn.commit()
    conn.close()
    return jsonify({"status": "ok", "completed": completed})

@app.route("/bingo-rules")
def bingo_rules():
    return render_template("bingo_rules.html")

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
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=activity_data.csv"})

@app.route("/pastwinners")
def pastwinners():
    athlete = request.args.get("athlete", "")
    return render_template("pastwinners.html", athlete=athlete)

init_db()
if __name__ == "__main__":
    app.run(debug=True)