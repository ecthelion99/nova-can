import os
import time
import argparse
import sqlite3

from nova_can.utils.compose_system import get_compose_result_from_env
from nova_can.communication import CanReceiver

# ---------- Filepaths ----------
os.environ.setdefault("NOVA_CAN_SYSTEMS_PATH", "/home/pi/nova-can/examples/systems")
os.environ.setdefault("NOVA_CAN_INTERFACES_PATH", "/home/pi/nova-can/examples/interfaces")
DB_FILE = os.environ.setdefault("NOVA_DATABASE_PATH", "/home/pi/nova-can/examples/databases/nova.db")


# ---------- Database Configuration ----------

# CLI DEFAULT values
MAX_ROWS_PER_TABLE = 1000 # max no. of data entries per table
COMMIT_INTERVAL = 1000 # conn.commit() after inserting this many data entries

insert_counter = 0 # initialise no. of inserts counter 


# ---------- Database Functions ----------
def setup_database(clear=False):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if clear:
        clear_database(conn, cursor)
    return conn, cursor

def clear_database(conn, cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    for table_name in tables:
        cursor.execute(f'DROP TABLE "{table_name[0]}"')
    conn.commit()

def insert_data(cursor, conn, topic, timestamp, value, verbose, max_rows):
    
    global insert_counter

    # create new table + trigger dynamically if required
    cursor.execute(f"""
        SELECT name FROM sqlite_master WHERE type='table' AND name=?;
    """, (topic,))
    table_exists = cursor.fetchone()

    if not table_exists:
        # create table
        cursor.execute(f""" 
            CREATE TABLE "{topic}" (
                timestamp TEXT,
                value REAL
            )
        """)
        # create trigger for this table
        trigger_name = f"limit_{topic}"
        cursor.execute(f"""
        CREATE TRIGGER "{trigger_name}"
        AFTER INSERT ON "{topic}"
        WHEN (SELECT COUNT(*) FROM "{topic}") > {max_rows}
        BEGIN
            DELETE FROM "{topic}"
            WHERE rowid = (SELECT MIN(rowid) FROM "{topic}");
        END;
        """)    
        conn.commit()

    # insert data entry
    cursor.execute(f"""
        INSERT INTO "{topic}" (timestamp, value)
        VALUES (?, ?)
    """, (timestamp, value))

    # batch conn.commit() 
    insert_counter += 1
    if insert_counter >= COMMIT_INTERVAL:
        conn.commit()
        insert_counter = 0

    if verbose:
        print(f"[CAN→DB] Inserted into '{topic}': {timestamp} -> {value}")

def update_max_rows_per_table(cursor, conn, max_rows):
    """Update existing table triggers to use new max_rows value from CLI."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    for (table_name,) in tables:
        trigger_name = f"limit_{table_name}"
        
        # drop existing trigger
        cursor.execute(f'DROP TRIGGER "{trigger_name}"')
        conn.commit()
        
        # create new trigger with updated max_rows
        cursor.execute(f"""
            CREATE TRIGGER "{trigger_name}"
            AFTER INSERT ON "{table_name}"
            WHEN (SELECT COUNT(*) FROM "{table_name}") > {max_rows}
            BEGIN
                DELETE FROM "{table_name}"
                WHERE rowid = (SELECT MIN(rowid) FROM "{table_name}");
            END;
        """)
        conn.commit()
        
        # immediately trim table if it exceeds the new limit
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        current_count = cursor.fetchone()[0]
        
        if current_count > max_rows:
            rows_to_delete = current_count - max_rows
            cursor.execute(f"""
                DELETE FROM "{table_name}"
                WHERE rowid IN (
                    SELECT rowid FROM "{table_name}"
                    ORDER BY rowid ASC
                    LIMIT {rows_to_delete}
                )
            """)
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

def can_to_db_callback(system_info, cursor, conn, max_rows, verbose):
    """Create a callback that bridges CAN messages to SQLite."""

    def callback(system_name: str, device_name: str, port: object, data: dict):
        dtype = get_device_type(system_info, device_name)
        topic = f"rover.{system_name}.{dtype}.{device_name}.{port.name}".lower()
        timestamp = str(int(time.time() * 1000))
        value = data["value"]

        insert_data(cursor, conn, topic, timestamp, value, verbose, max_rows) # publish data entry to db table

    return callback

# ---------- Start CAN Receiver & Database ----------
def start_gateway(max_rows=MAX_ROWS_PER_TABLE, clear_db=True, verbose=False):
    """
    Start the CAN→DB gateway.
    :param max_rows: max no. data entries per table
    :param clear_db: clear db before starting can receiver (default = true)
    :param verbose: Print DB inserts to console
    """

    conn, cursor = setup_database(clear=clear_db)

    if not clear_db: # for an existing db, update table capacity to new limit entered via CLI 
        update_max_rows_per_table(cursor, conn, max_rows) 

    compose_result = get_compose_result_from_env()
    if not compose_result or not compose_result.success:
        raise RuntimeError(f"Failed to compose system: {compose_result.errors}")
    system_info = compose_result.system

    """Start listening to CAN messages and forwarding them to DB."""
    receiver = CanReceiver(system_info, can_to_db_callback(system_info, cursor, conn, max_rows, verbose)) 
    receiver.run()

# ---------- Command-Line Interface ----------
def start_gateway_cli():
    parser = argparse.ArgumentParser(
        description="Starts a CAN to DB gateway that listens for CAN messages and inserts them into SQLite.\n "
                    "The file path to the system info (.yaml files) needs to be provided via environment variables.\n "
                    "NOVA_CAN_INTERFACES_PATH and NOVA_CAN_SYSTEMS_PATH"
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Print DB inserts to console")
    parser.add_argument("-m", "--max-rows", type=int, default=MAX_ROWS_PER_TABLE, help="Maximum number of rows to keep per table")
    parser.add_argument("-c", "--clear-db", action="store_true", help="Clear the database before inserting CAN data")

    args = parser.parse_args()
    start_gateway(max_rows=args.max_rows, clear_db=args.clear_db, verbose=args.verbose)

# ---------- Default Usage ----------
if __name__ == "__main__":
    start_gateway_cli()
