from flask import Flask, request, jsonify, g
import time
import sqlite3
import os
import json

app = Flask(__name__)

# ---------- Database Configuration ----------
DB_FILE = os.environ.setdefault("NOVA_DATABASE_PATH", "/home/pih/FYP/nova-can/examples/databases/nova.db")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row  # lets us access rows like dicts
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

@app.teardown_appcontext
def teardown_db(exception):
    close_db()


# This route will catch any path under /rover
@app.route("/rover/<path:subpath>", methods=["GET"])
def get_table(subpath):
    time_lower = request.args.get("time_lower")
    time_upper = request.args.get("time_upper")

    db = get_db()
    cursor = db.cursor()

    table = subpath.replace("/", ".")  # Convert slashes to dots for table naming

    query = f"""
        SELECT timestam, value
        FROM {table}
        WHERE timestam BETWEEN ? AND ?
        ORDER BY timestam ASC
    """
    cursor.execute(query, (time_lower, time_upper))
    rows = cursor.fetchall()

    # jsonify handles conversion to JSON
    # In Flask, what you return from a route function becomes the HTTP response:
    # 200 is the HTTP status code for OK
    # Data + status code + headers
    result = [{"timestam": row["timestam"], "value": row["value"]} for row in rows]
    return jsonify(result), 200, {'Content-Type': 'application/json'}

if __name__ == "__main__":
    # setup database connection


    # Start the server on localhost:8080 listening on all network interfaces
    print("Starting server on http://localhost:8080 ...")
    # Threaded = true allows handling multiple requests at once
    app.run(host="0.0.0.0", port=8080, debug=True, threaded=True)
    
