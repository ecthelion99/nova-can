from flask import Flask, request, jsonify, g
import time
import sqlite3
import os
import json
import argparse

app = Flask(__name__)

# ---------- Database Configuration ----------
#fp = r"C:\Users\harry\Documents\FYP code\nova-can\examples\databases\nova.db".replace("\\", "/")
#DB_FILE = os.environ.setdefault("NOVA_DATABASE_PATH", fp)
DB_FILE = os.environ.setdefault("NOVA_DATABASE_PATH", "/home/pi/nova-can/examples/databases/nova.db")

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
    # These might need to change
    start = request.args.get("start")
    end = request.args.get("end")

    db = get_db()
    cursor = db.cursor()

    table = "rover." + subpath.replace("/", ".")


    try:
        query = f"""
            SELECT timestamp, value
            FROM "{table}"
            WHERE timestamp BETWEEN ? AND ?
            ORDER BY timestamp ASC
        """
        cursor.execute(query, (start, end))
        rows = cursor.fetchall()
    # if exception occurs, return 404 error
    except sqlite3.OperationalError:
        return jsonify({"error": f"Table '{table}' does not exist"}), 404 # error 404 = not found

    # In Flask, what you return from a route function becomes the HTTP response:
    # 200 is the HTTP status code for OK
    # Data + status code + headers
    result = [{"timestamp": row["timestamp"], "value": row["value"]} for row in rows]
    response = jsonify(result)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response, 200#, {'Content-Type': 'application/json'} # 200 = OK

#
def start_gateway(debug_in=False, port_in=9000):
    # Start the server on localhost:8080 listening on all network interfaces
    print("Starting server on http://localhost:{port} ...")
    # Threaded = true allows handling multiple requests at once
    app.run(host="0.0.0.0", port=port_in, debug=debug_in, threaded=True)

# ---------- Command-Line Interface ----------
def start_gateway_cli():
    parser = argparse.ArgumentParser(
        description="Handles HTTP requests from openMCT.\n "
                    "The file path to the system info (.yaml files) needs to be provided via environment variables.\n "
                    "NOVA_CAN_INTERFACES_PATH and NOVA_CAN_SYSTEMS_PATH"
                    "NOVA_DATABASE_PATH also required (path to SQLite database)"
    )
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print DB inserts to console, True or False, default False")
    parser.add_argument("-p", "--port", type=int, default=9000,
                        help="Port to run HTTP server on, default 9000")
    
    
    args = parser.parse_args()
    start_gateway(debug_in=args.verbose, port_in = args.port)


if __name__ == "__main__":
    start_gateway(debug_in=True)
    
