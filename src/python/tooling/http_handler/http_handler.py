from flask import Flask, request, jsonify, g
import sqlite3
import os
import argparse
import logging

app = Flask(__name__)

# ---------- Database Configuration ----------
DB_FILE = os.environ.get(
    "NOVA_DATABASE_PATH", "/home/pi/nova-can/examples/databases/nova.db"
)


def get_db():
    """
    Open the DB in read-only mode so we do NOT create the file if it doesn't exist.
    Raises sqlite3.OperationalError when the file is missing or unreadable.
    """
    if "db" not in g:
        uri = f"file:{DB_FILE}?mode=ro"
        g.db = sqlite3.connect(uri, uri=True)
        g.db.row_factory = sqlite3.Row  # lets us access rows like dicts
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.teardown_appcontext
def teardown_db(exception):
    close_db()


# Helper to serialize row values safely for JSON
def _serialize_row_to_dict(row):
    """
    Convert sqlite3.Row to a plain dict. Since the DB stores only strings and numbers,
    we simply return those values. If any bytes do appear unexpectedly, omit them.
    Also renames 'utc' column to 'timestamp' in the output.
    """
    result = {}
    for k in row.keys():
        if isinstance(row[k], (bytes, bytearray)):
            continue
        # Rename 'utc' to 'timestamp' in the output
        key = "timestamp" if k.lower() == "utc" else k
        result[key] = row[k]
    return result


# This route will catch any path under /rover
@app.route("/rover/<path:subpath>", methods=["GET"])
def get_table(subpath):
    # Query params
    start = request.args.get("start")
    end = request.args.get("end")

    # Validate start & end are provided
    if start is None or end is None:
        return (
            jsonify({"error": "Both 'start' and 'end' query parameters are required"}),
            400,
        )

    # Trim whitespace
    start = start.strip()
    end = end.strip()

    # Optionally validate numeric ordering if they can be parsed as numbers
    try:
        s_num = float(start)
        e_num = float(end)
        if s_num > e_num:
            return jsonify({"error": "'start' must be <= 'end'"}), 400
    except ValueError:
        # Not numeric — leave as-is (e.g. ISO utcs). We don't enforce ordering for non-numeric strings.
        pass

    # Try to open DB read-only (prevents accidental creation)
    try:
        db = get_db()
    except sqlite3.OperationalError:
        return jsonify({"error": "Database file not found or not accessible"}), 500

    cursor = db.cursor()

    # Build table identifier (same approach as before)
    table = "rover." + subpath.replace("/", ".")

    try:
        # Select all columns so we can dynamically discover column names
        query = f"""
            SELECT *
            FROM "{table}"
            WHERE utc BETWEEN ? AND ?
            ORDER BY utc ASC
        """
        cursor.execute(query, (start, end))
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        print("Database query error for table:", table)
        # Could be table missing, or missing column 'utc' used in WHERE — return 404 for missing table/structure
        return (
            jsonify(
                {
                    "error": f"Table '{table}' does not exist or is missing required columns"
                }
            ),
            404,
        )

    # If rows exist, ensure 'utc' column is present (defensive check)
    if rows:
        first_row = rows[0]
        if "utc" not in first_row.keys():
            return (
                jsonify({"error": "Table does not contain required 'utc' column"}),
                500,
            )

    # Convert each sqlite3.Row into a dict of column->value (no special blob handling)
    result = [_serialize_row_to_dict(row) for row in rows]

    response = jsonify(result)
    response.headers.add("Access-Control-Allow-Origin", "*")
    return response, 200


#
def start_gateway(debug_in=False, port_in=9000, verbose_in=False):
    print(f"Starting server on http://localhost:{port_in} ...")

    if verbose_in:
        logging.basicConfig(level=logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)
        app.logger.debug("Verbose logging enabled")

    app.run(host="0.0.0.0", port=port_in, debug=debug_in, threaded=True)


# ---------- Command-Line Interface ----------
def start_gateway_cli():
    parser = argparse.ArgumentParser(
        description=(
            "Handles HTTP requests from openMCT.\n "
            "The file path to the system info (.yaml files) needs to be provided via environment variables: "
            "NOVA_CAN_INTERFACES_PATH and NOVA_CAN_SYSTEMS_PATH. "
            "NOVA_DATABASE_PATH also required (path to SQLite database)."
        )
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging (prints additional server logs).",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=9000,
        help="Port to run HTTP server on, default 9000",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Run Flask in debug mode (do not use in production)",
    )

    args = parser.parse_args()
    start_gateway(debug_in=args.debug, port_in=args.port, verbose_in=args.verbose)


if __name__ == "__main__":
    # NOTE: unchanged from before: runs in debug mode when executed directly
    start_gateway(debug_in=True)
