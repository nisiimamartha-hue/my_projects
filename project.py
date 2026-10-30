"""School Management System
Console app using only the Python standard library (SQLite for storage).
Run:  python school_sy
"""
import sqlite3
from datetime import date

DB_FILE = "school.db"



def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        dob TEXT,
        class_level TEXT
    );
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        teacher TEXT
    );
    CREATE TABLE IF NOT EXISTS enrollments (
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        course_id  INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
        PRIMARY KEY (student_id, course_id)
    );
    CREATE TABLE IF NOT EXISTS grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        course_id  INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
        assessment TEXT NOT NULL,
        score REAL NOT NULL,
        max_score REAL NOT NULL DEFAULT 100
    );
    CREATE TABLE IF NOT EXISTS attendance (
        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
        course_id  INTEGER NOT NULL REFERENCES courses(id)  ON DELETE CASCADE,
        day TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('present', 'absent', 'late')),
        PRIMARY KEY (student_id, course_id, day)
    );
    """)
    conn.commit()


# ---------- Input helpers ----------
def ask(prompt, required=True):
    while True:
        value = input(prompt).strip()
        if value or not required:
            return value
        print("  This field is required.")


def ask_int(prompt):
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("  Please enter a whole number.")


def ask_float(prompt, minimum=None, maximum=None):
    while True:
        try:
            value = float(input(prompt).strip())
        except ValueError:
            print("  Please enter a number.")
            continue
        if minimum is not None and value < minimum:
            print(f"  Must be at least {minimum}.")
        elif maximum is not None and value > maximum:
            print(f"  Must be at most {maximum}.")
        else:
            return value


def ask_date(prompt):
    while True:
        raw = input(prompt).strip() or date.today().isoformat()
        try:
            return date.fromisoformat(raw).isoformat()
        except ValueError:
            print("  Use the format YYYY-MM-DD (Enter for today).")


def letter_grade(pct):
    for cutoff, letter in ((80, "A"), (70, "B"), (60, "C"), (50, "D")):
        if pct >= cutoff:
            return letter
    return "F"


def student_exists(conn, sid):
    return conn.execute("SELECT 1 FROM students WHERE id = ?", (sid,)).fetchone()


def course_exists(conn, cid):
    return conn.execute("SELECT 1 FROM courses WHERE id = ?", (cid,)).fetchone()


# ---------- Features ----------
def add_student(conn):
    name = ask("Full name: ")
    dob = ask("Date of birth (YYYY-MM-DD, optional): ", required=False)
    level = ask("Class/Year (e.g. Year 9): ", required=False)
    cur = conn.execute(
        "INSERT INTO students (name, dob, class_level) VALUES (?, ?, ?)",
        (name, dob, level),
    )
    conn.commit()
    print(f"  Student added with ID {cur.lastrowid}.")


def list_students(conn):
    rows = conn.execute("SELECT * FROM students ORDER BY name").fetchall()
    if not rows:
        print("  No students yet.")
        return
    print(f"\n{'ID':<5}{'Name':<28}{'DOB':<13}{'Class'}")
    print("-" * 60)
    for r in rows:
        print(f"{r['id']:<5}{r['name']:<28}{r['dob'] or '-':<13}{r['class_level'] or '-'}")


def add_course(conn):
    code = ask("Course code (e.g. MATH101): ").upper()
    title = ask("Course title: ")
    teacher = ask("Teacher name: ", required=False)
    try:
        cur = conn.execute(
            "INSERT INTO courses (code, title, teacher) VALUES (?, ?, ?)",
            (code, title, teacher),
        )
        conn.commit()
        print(f"  Course added with ID {cur.lastrowid}.")
    except sqlite3.IntegrityError:
        print("  A course with that code already exists.")


def list_courses(conn):
    rows = conn.execute("""
        SELECT c.*, COUNT(e.student_id) AS enrolled
        FROM courses c LEFT JOIN enrollments e ON e.course_id = c.id
        GROUP BY c.id ORDER BY c.code
    """).fetchall()
    if not rows:
        print("  No courses yet.")
        return
    print(f"\n{'ID':<5}{'Code':<10}{'Title':<28}{'Teacher':<20}{'Enrolled'}")
    print("-" * 72)
    for r in rows:
        print(f"{r['id']:<5}{r['code']:<10}{r['title']:<28}{r['teacher'] or '-':<20}{r['enrolled']}")


def enroll(conn):
    sid = ask_int("Student ID: ")
    cid = ask_int("Course ID: ")
    if not student_exists(conn, sid) or not course_exists(conn, cid):
        print("  Student or course not found.")
        return
    try:
        conn.execute("INSERT INTO enrollments VALUES (?, ?)", (sid, cid))
        conn.commit()
        print("  Enrolled.")
    except sqlite3.IntegrityError:
        print("  Student is already enrolled in that course.")


def is_enrolled(conn, sid, cid):
    return conn.execute(
        "SELECT 1 FROM enrollments WHERE student_id = ? AND course_id = ?", (sid, cid)
    ).fetchone()


def record_grade(conn):
    sid = ask_int("Student ID: ")
    cid = ask_int("Course ID: ")
    if not is_enrolled(conn, sid, cid):
        print("  That student is not enrolled in that course.")
        return
    assessment = ask("Assessment name (e.g. Quiz 1, Midterm): ")
    max_score = ask_float("Maximum score: ", minimum=1)
    score = ask_float("Score obtained: ", minimum=0, maximum=max_score)
    conn.execute(
        "INSERT INTO grades (student_id, course_id, assessment, score, max_score) "
        "VALUES (?, ?, ?, ?, ?)",
        (sid, cid, assessment, score, max_score),
    )
    conn.commit()
    print(f"  Recorded {score:g}/{max_score:g} ({letter_grade(score / max_score * 100)}).")


def mark_attendance(conn):
    cid = ask_int("Course ID: ")
    if not course_exists(conn, cid):
        print("  Course not found.")
        return
    day = ask_date("Date (YYYY-MM-DD, Enter for today): ")
    students = conn.execute(
        "SELECT s.id, s.name FROM students s "
        "JOIN enrollments e ON e.student_id = s.id "
        "WHERE e.course_id = ? ORDER BY s.name", (cid,)
    ).fetchall()
    if not students:
        print("  No students enrolled in this course.")
        return
    codes = {"p": "present", "a": "absent", "l": "late"}
    for s in students:
        while True:
            key = input(f"  {s['name']} [p]resent/[a]bsent/[l]ate (Enter = present): ").strip().lower() or "p"
            if key in codes:
                break
            print("  Enter p, a or l.")
            "INSERT OR REPLACE INTO attendance VALUES (?, ?, ?, ?)",
            (s["id"], cid, day, codes
        )
    conn.commit()
    


def report_card(conn):
    sid = ask_int("Student ID: ")
    student = conn.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
    if not student:
        print("  Student not found.")
        return
    print(f"\n=== Report Card: {student['name']} ({student['class_level'] or 'no class'}) ===")
    courses = conn.execute(
        "SELECT c.id, c.code, c.title FROM courses c "
        "JOIN enrollments e ON e.course_id = c.id "
        "WHERE e.student_id = ? ORDER BY c.code", (sid,)
    ).fetchall()
    if not courses:
        print("  Not enrolled in any courses.")
        return
    print(f"{'Course':<30}{'Average':>9}{'Grade':>7}{'Attendance':>13}")
    print("-" * 59)
    averages = []
    for c in courses:
        g = conn.execute(
            "SELECT SUM(score) AS s, SUM(max_score) AS m FROM grades "
            "WHERE student_id = ? AND course_id = ?", (sid, c["id"])
        ).fetchone()
        if g["m"]:
            pct = g["s"] / g["m"] * 100
            averages.append(pct)
            avg_txt, letter = f"{pct:.1f}%", letter_grade(pct)
        else:
            avg_txt, letter = "-", "-"
        a = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(status IN ('present', 'late')) AS came "
            "FROM attendance WHERE student_id = ? AND course_id = ?", (sid, c["id"])
        ).fetchone()
        att_txt = f"{a['came'] / a['total'] * 100:.0f}%" if a["total"] else "-"
        print(f"{c['code'] + ' ' + c['title']:<30}{avg_txt:>9}{letter:>7}{att_txt:>13}")
    if averages:
        overall = sum(averages) / len(averages)
        print("-" * 59)
        print(f"Overall average: {overall:.1f}% ({letter_grade(overall)})")


def course_roster(conn):
    cid = ask_int("Course ID: ")
    course = conn.execute("SELECT * FROM courses WHERE id = ?", (cid,)).fetchone()
    if not course:
        print("  Course not found.")
        return
    print(f"\n=== {course['code']} - {course['title']} (Teacher: {course['teacher'] or '-'}) ===")
    rows = conn.execute("""
        SELECT s.id, s.name,
               (SELECT SUM(score) * 100.0 / SUM(max_score) FROM grades g
                WHERE g.student_id = s.id AND g.course_id = e.course_id) AS pct
        FROM students s JOIN enrollments e ON e.student_id = s.id
        WHERE e.course_id = ? ORDER BY s.name
    """, (cid,)).fetchall()
    if not rows:
        print("  No students enrolled.")
        return
    for r in rows:
        avg = f"{r['pct']:.1f}% ({letter_grade(r['pct'])})" if r["pct"] is not None else "no grades"
        print(f"  {r['id']:<5}{r['name']:<28}{avg}")


def delete_student(conn):
    sid = ask_int("Student ID to delete: ")
    if not student_exists(conn, sid):
        print("  Student not found.")
        return
    if ask("  Delete this student and all their records? (y/n): ").lower() == "y":
        conn.execute("DELETE FROM students WHERE id = ?", (sid,))
        conn.commit()
        print("  Deleted.")


# ---------- Main menu ----------
MENU = [
    ("Add student",
    ("List students", list_students),
    ("Add course", add_course),
    ("List courses", list_courses),
    ("Enroll student in course", enroll),
    ("Record a grade", record_grade),
    ("Mark attendance", mark_attendance),
    ("Student report card", report_card),
    ("Course roster", course_roster),
    ("Delete student", delete_student),
]


def main():
    conn = connect()
    init_db(conn)
    while True:
        print("\n===== SCHOOL MANAGEMENT SYSTEM =====")
        for i, (label, _) in enumerate(MENU, 1):
            print(f"  {i:>2}. {label}")
        print("   0. Exit")
        try:
            choice = input("Choose: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if choice == "0":
            break
        if choice.isdigit() and 1 <= int(choice) <= len(MENU):
            try:
                MENU[int(choice) - 1][1](conn)
            except (EOFError, KeyboardInterrupt):
                print("\n  Cancelled.")
        else:
            print("  Invalid choice.")
    conn.close()
    print("Goodbye!")


if __name__ == "__main__":
    main()