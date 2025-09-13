from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, get_flashed_messages
from flask_socketio import SocketIO, join_room, leave_room, emit
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecret"
socketio = SocketIO(app)

DB = "database.db"

# -----------------------
# Database init
# -----------------------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT
    )''')
    # Groups
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        group_name TEXT PRIMARY KEY,
        admin TEXT
    )''')
    # Members
    c.execute('''CREATE TABLE IF NOT EXISTS members (
        group_name TEXT,
        username TEXT
    )''')
    # Messages
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        group_name TEXT,
        sender TEXT,
        text TEXT,
        timestamp TEXT,
        seen_by TEXT
    )''')
    # Join requests
    c.execute('''CREATE TABLE IF NOT EXISTS join_requests (
        group_name TEXT,
        username TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

# -----------------------
# Routes
# -----------------------
@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        row = c.fetchone()
        conn.close()

        if not row:
            flash("❌ Invalid username or password.")
            return redirect(url_for("login"))

        session["username"] = username
        flash("✅ Welcome back!")
        return redirect(url_for("home"))

    return render_template("login.html")



from flask import flash

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB)
        c = conn.cursor()

        # check if username already exists
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        if c.fetchone():
            conn.close()
            flash("⚠️ Username already exists! Please choose another.")
            return redirect(url_for("register"))

        # insert new user
        c.execute("INSERT INTO users VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()

        flash("✅ Registration successful! Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

@app.route("/home")
def home():
    if "username" not in session:
        return redirect(url_for("login"))
    username = session["username"]
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Load all groups
    c.execute("SELECT group_name, admin FROM groups")
    all_groups = {row[0]: {"admin": row[1]} for row in c.fetchall()}

    # Load join requests only for groups where current user is admin
    c.execute("SELECT group_name, username FROM join_requests")
    join_requests = {}
    for row in c.fetchall():
        group_name, user_req = row
        if all_groups.get(group_name) and all_groups[group_name]["admin"] == username:
            join_requests.setdefault(group_name, []).append(user_req)

    # Load all memberships
    c.execute("SELECT group_name, username FROM members")
    memberships = {}
    for row in c.fetchall():
        group_name, user_mem = row
        memberships.setdefault(group_name, set()).add(user_mem)

    # NEW: Load joined groups for current user
    c.execute("SELECT group_name FROM members WHERE username=?", (username,))
    joined_groups = [row[0] for row in c.fetchall()]

    conn.close()
    return render_template(
        "home.html",
        username=username,
        all_groups=all_groups,
        join_requests=join_requests,
        memberships=memberships,
        joined_groups=joined_groups   # send joined groups
    )

@app.route("/search_groups")
def search_groups():
    """Search groups by keyword"""
    if "username" not in session:
        return jsonify({"error": "Not logged in"}), 401
    q = request.args.get("q", "").lower()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT group_name, admin FROM groups WHERE LOWER(group_name) LIKE ?", (f"%{q}%",))
    groups = [{"group_name": row[0], "admin": row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify(groups)

@app.route("/create_group", methods=["POST"])
def create_group():
    if "username" not in session:
        return jsonify({"error":"Not logged in"}),401
    data = request.get_json()
    group_name = data.get("group_name")
    if not group_name:
        return jsonify({"error":"Group name required"}),400
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO groups VALUES (?,?)",(group_name,session["username"]))
        c.execute("INSERT INTO members VALUES (?,?)",(group_name,session["username"]))
        conn.commit()
        return jsonify({"success":True})
    except:
        return jsonify({"error":"Group exists"}),400
    finally:
        conn.close()

@app.route("/request_join/<group_name>", methods=["POST"])
def request_join(group_name):
    if "username" not in session:
        return jsonify({"error":"Not logged in"}),401
    user = session["username"]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Prevent requesting if already a member
    c.execute("SELECT * FROM members WHERE group_name=? AND username=?", (group_name,user))
    if c.fetchone():
        conn.close()
        return jsonify({"error":"Already a member"}),400
    # Prevent duplicate requests
    c.execute("SELECT * FROM join_requests WHERE group_name=? AND username=?",(group_name,user))
    if c.fetchone():
        conn.close()
        return jsonify({"error":"Already requested"}),400
    c.execute("INSERT INTO join_requests VALUES (?,?)",(group_name,user))
    conn.commit()
    conn.close()
    return jsonify({"success":True})

@app.route("/approve/<group_name>/<username>")
def approve(group_name, username):
    if "username" not in session:
        return redirect(url_for("login"))
    user = session["username"]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT admin FROM groups WHERE group_name=?",(group_name,))
    row = c.fetchone()
    if row and row[0]==user:
        # Add as member
        c.execute("INSERT INTO members VALUES (?,?)",(group_name,username))
        # Remove join request
        c.execute("DELETE FROM join_requests WHERE group_name=? AND username=?",(group_name,username))
        conn.commit()
    conn.close()
    return redirect(url_for("home"))

@app.route("/delete_group/<group_name>", methods=["POST"])
def delete_group(group_name):
    if "username" not in session:
        return jsonify({"error":"Not logged in"}),401
    user = session["username"]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT admin FROM groups WHERE group_name=?",(group_name,))
    row = c.fetchone()
    if not row or row[0]!=user:
        conn.close()
        return jsonify({"error":"Not authorized"}),403
    c.execute("DELETE FROM groups WHERE group_name=?",(group_name,))
    c.execute("DELETE FROM members WHERE group_name=?",(group_name,))
    c.execute("DELETE FROM messages WHERE group_name=?",(group_name,))
    c.execute("DELETE FROM join_requests WHERE group_name=?",(group_name,))
    conn.commit()
    conn.close()
    return jsonify({"success":True})

@app.route("/chat/<group_name>")
def chat(group_name):
    if "username" not in session:
        return redirect(url_for("login"))
    username = session["username"]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Check if user is member
    c.execute("SELECT * FROM members WHERE group_name=? AND username=?",(group_name,username))
    if not c.fetchone():
        conn.close()
        return "You are not a member of this group."
    # Load messages
    c.execute("SELECT sender, text, timestamp, seen_by FROM messages WHERE group_name=?",(group_name,))
    messages=[]
    for row in c.fetchall():
        seen = row[3].split(",") if row[3] else []
        messages.append({"sender":row[0],"text":row[1],"timestamp":row[2],"seen_by":seen})
    # Load group admin
    c.execute("SELECT admin FROM groups WHERE group_name=?",(group_name,))
    admin = c.fetchone()[0]
    # Load online users
    c.execute("SELECT username FROM members WHERE group_name=?",(group_name,))
    online_users=[r[0] for r in c.fetchall()]
    conn.close()
    return render_template("chat.html", username=username, group=group_name, messages=messages, admin=admin, online_users=online_users)

# -----------------------
# SocketIO
# -----------------------
online = {}

@socketio.on("join_room")
def on_join(data):
    username = data["username"]
    room = data["room"]
    join_room(room)
    online.setdefault(room,set()).add(username)
    emit("update_online", list(online[room]), room=room)

@socketio.on("send_message")
def send_message(data):
    username = data["username"]
    room = data["room"]
    text = data["text"]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Save message
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO messages VALUES (?,?,?,?,?)",(room,username,text,timestamp,username))
    conn.commit()
    # Fetch all messages in room to update seen_by
    c.execute("SELECT rowid,sender,text,seen_by FROM messages WHERE group_name=?",(room,))
    all_msgs=[]
    for row in c.fetchall():
        seen = row[3].split(",") if row[3] else []
        if username not in seen:
            seen.append(username)
            c.execute("UPDATE messages SET seen_by=? WHERE rowid=?",(",".join(seen),row[0]))
        all_msgs.append({"sender":row[1],"text":row[2],"seen_by":seen})
    conn.commit()
    conn.close()
    emit("receive_message", {"sender":username,"text":text,"seen_by":[username]}, room=room)

@socketio.on("disconnect")
def on_disconnect():
    for room, users in online.items():
        if session.get("username") in users:
            users.remove(session["username"])
            emit("update_online", list(users), room=room)

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
