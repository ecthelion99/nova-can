import os
import time
import argparse
import sqlite3

from nova_can.utils.compose_system import get_compose_result_from_env
from nova_can.communication import CanReceiver

# ---------- Default Configuration ----------
os.environ.setdefault("NOVA_CAN_SYSTEMS_PATH", "/home/pih/FYP/nova-can/examples/systems")
os.environ.setdefault("NOVA_CAN_INTERFACES_PATH", "/home/pih/FYP/nova-can/examples/interfaces")


# ---------- Database Configuration ----------
DB_FILE = "/databases/nova.db" # db location
MAX_ROWS_PER_TABLE = 10 # max no. of data entries per table

def setup_database(clear=False):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if clear:
        clear_database(conn, cursor)
    return conn, cursor


# ---------- Database Functions ----------
def clear_database(conn, cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table_name in tables:
        cursor.execute(f'DROP TABLE IF EXISTS "{table_name[0]}"')
    conn.commit()
    
def create_table_dynamically(cursor, conn, topic, max_rows): # dynamic table creator
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS "{topic}" (
            timestamp TEXT,
            value REAL
        )
    """)
    conn.commit()

    trigger_name = f"limit_rows_after_insert_{topic}" # sql 'trigger' for max data entries
    cursor.execute(f"""
        CREATE TRIGGER IF NOT EXISTS "{trigger_name}"
        AFTER INSERT ON "{topic}"
        BEGIN
            DELETE FROM "{topic}"
            WHERE rowid NOT IN (
                SELECT rowid FROM "{topic}"
                ORDER BY timestamp DESC
                LIMIT {max_rows}
            );
        END;
    """)
    conn.commit()

def insert_data(cursor, conn, topic, timestamp, value):
    cursor.execute(f"""
        INSERT INTO "{topic}" (timestamp, value)
        VALUES (?, ?)
    """, (timestamp, value))
    conn.commit()


# ---------- Helper Functions ----------
def get_device_type(system_info, device_name: str) -> str:
    """Retrieve the device type for a given device from the composed system info."""
    if system_info is None:
        raise ValueError("system_info must be provided")

    device = system_info.devices.get(device_name)
    if device is None:
        raise ValueError(f"Device '{device_name}' not found in system '{system_info.name}'")

    return device.device_type

def can_to_db_callback(system_info, cursor, conn, max_rows, verbose: bool = True):
    """Create a callback that bridges CAN messages to SQLite."""
    def callback(system_name: str, device_name: str, port: object, data: dict):
        dtype = get_device_type(system_info, device_name)
        topic = f"{system_name}_{dtype}_{device_name}_{port.name}".lower()
        timestamp = str(int(time.time() * 1000))
        value = data["value"]

        create_table_dynamically(cursor, conn, topic, max_rows) # dynamically create table if required
        insert_data(cursor, conn, topic, timestamp, value) # publish data entry to db table

        if verbose:
            print(f"[CAN→DB] Inserted into '{topic}': {timestamp} -> {value}")
    return callback


# ---------- CAN Receiver & Database Start ----------
def start_can_receiver(system_info, max_rows, clear_db, verbose: bool = True):

    conn, cursor = setup_database(clear=clear_db) # access database

    """Start listening to CAN messages and forwarding them to DB."""
    receiver = CanReceiver(system_info, can_to_db_callback(system_info, cursor, conn, max_rows, verbose)) 
    receiver.run()


# ---------- Public API ----------
def start_gateway(max_rows=MAX_ROWS_PER_TABLE, clear_db=True, verbose=False):
    """
    Start the CAN→DB gateway.
    :param max_rows: max no. data entries per table
    :param clear_db: clear db before starting can receiver (default = true)
    :param verbose: Print DB inserts to console
    """

    conn, cursor = setup_database(clear=clear_db)

    compose_result = get_compose_result_from_env()
    if not compose_result or not compose_result.success:
        raise RuntimeError(f"Failed to compose system: {compose_result.errors}")
    system_info = compose_result.system

    start_can_receiver(system_info, max_rows, clear_db, verbose)


# ---------- Command-Line Interface ----------
def start_gateway_cli():
    parser = argparse.ArgumentParser(
        description="Starts a CAN to DB gateway that listens for CAN messages and inserts them into SQLite.\n "
                    "The file path to the system info (.yaml files) needs to be provided via environment variables.\n "
                    "NOVA_CAN_INTERFACES_PATH and NOVA_CAN_SYSTEMS_PATH"
    )
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print DB inserts to console, True or False, default False")
    
    parser.add_argument("--max-rows", type=int, default=MAX_ROWS_PER_TABLE,
                        help="Maximum number of rows to keep per table")
    
    parser.add_argument("--clear-db", action="store_true",
        help="Clear the database before inserting CAN data, True or False, default False")

    args = parser.parse_args()
    start_gateway(max_rows=args.max_rows, clear_db=args.clear_db, verbose=args.verbose)


# ---------- Default Usage ----------
if __name__ == "__main__":
    start_gateway(max_rows=MAX_ROWS_PER_TABLE, clear_db=True, verbose=True)
