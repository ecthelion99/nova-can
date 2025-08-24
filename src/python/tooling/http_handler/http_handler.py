from flask import Flask, request, jsonify
import time

app = Flask(__name__)

# This route will catch any path under /rover
@app.route("/rover/<path:subpath>", methods=["GET"])
def handle_rover(subpath):
    # Print to terminal so we can see what was requested
    value = request.args.get("value")

    # Print the full path and value to the terminal
    full_path = request.path
    print(f"Received GET request on {full_path} with value={value}")

    # Construct the response as a JSON string with timestamp and value
    response = f'{{"timestamp": {int(time.time() * 1000)}, "value": {value}}}'

    # In Flask, what you return from a route function becomes the HTTP response:
    # 200 is the HTTP status code for OK
    # Data + status code + headers
    return response, 200, {'Content-Type': 'application/json'}

if __name__ == "__main__":
    # Start the server on localhost:8080 listening on all network interfaces
    print("Starting server on http://localhost:8080 ...")
    app.run(host="0.0.0.0", port=8080, debug=True, threaded=True)
