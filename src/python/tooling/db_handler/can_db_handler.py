import os
import time
import argparse
import sqlite3

from typing import List, Dict, Any
from nova_can.utils.compose_system import get_compose_result_from_env
from tooling.openMCT_system_compiler.compile_system import (
load_composed_system_dict,
    build_openmct_dict,
)
from tooling.mqtt_handler.can_mqtt_handler import (
    get_device_type,
    flatten_dict,
    all_bools,
)
from nova_can.communication import CanReceiver

# ---------- Filepaths ----------
os.environ.setdefault("NOVA_CAN_SYSTEMS_PATH", "/home/pi/nova-can/examples/systems")
os.environ.setdefault(
    "NOVA_CAN_INTERFACES_PATH", "/home/pi/nova-can/examples/interfaces"
)
DB_FILE = os.environ.setdefault(
    "NOVA_DATABASE_PATH", "/home/pi/nova-can/examples/databases/nova.db"
)

# ---------- Default Configuration (can be overridden via env) ----------
DEFAULT_MQTT_TOPIC_PREFIX = os.environ.get("NOVA_CAN_MQTT_TOPIC_PREFIX", "rover")

# ---------- Database Configuration ----------

# CLI DEFAULT values
MAX_ROWS_PER_TABLE = 10000  # max no. of data entries per table
COMMIT_INTERVAL = 1000  # conn.commit() after inserting this many data entries

insert_counter = 0  # initialise no. of inserts counter


# ---------- Database Functions ----------
def create_all_tables(cursor, conn, node, max_rows):

    def create_table_and_trigger(table_name: str, items_values: List[Dict[str, Any]]):

        # create table
        sql_cols = []
        for col in items_values:
            col_name = col["key"]

            fmt = col.get("format")
            if fmt == "bool":
                col_type = "TEXT"  # store bools as "True"/"False" strings in SQL
            else:
                col_type = "INTEGER"  # all other numeric types as INTEGER in SQL

            sql_cols.append(f'"{col_name}" {col_type}')

        sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(sql_cols)});'
        cursor.execute(sql)

        # create trigger for the table that limits max no. of rows
        trigger_name = f"limit_{table_name}"

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name=?;",
            (trigger_name,),
        )
        if not cursor.fetchone():  # if trigger does not exist already
            cursor.execute(
                f"""
                CREATE TRIGGER "{trigger_name}"
                AFTER INSERT ON "{table_name}"
                WHEN (SELECT COUNT(*) FROM "{table_name}") > {max_rows}
                BEGIN
                    DELETE FROM "{table_name}"
                    WHERE rowid = (SELECT MIN(rowid) FROM "{table_name}");
                END;
                """
            )

    def _recurse(node):
        if isinstance(node, dict):
            # for every Transmit group, inspect its items - a list of dictionaries for each topic
            if node.get("name") == "Transmit":
                items = node.get("items", [])
                for it in items: # for each topic
                    if isinstance(it, dict) and "key" in it and "values" in it:

                        topic = it["key"] 
                        values = it["values"]

                        create_table_and_trigger(topic, values)

            # Recurse into all dict values to find nested 'items' lists
            for v in node.values():
                if isinstance(v, (dict, list)):
                    _recurse(v)

        elif isinstance(node, list):
            for elem in node:
                if isinstance(elem, (dict, list)):
                    _recurse(elem)

    _recurse(node)
    conn.commit()


def insert_data(cursor, conn, topic, data_dict):
    """
    Insert data into a table with arbitrary columns.
    - data_dict: dict of {column_name: value}, e.g. {'timestamp': 123, 'x': 1.5, 'y': 2.3}
    """
    global insert_counter

    # Prepare columns and placeholders
    columns = ", ".join([f'"{col}"' for col in data_dict.keys()])
    placeholders = ", ".join(["?"] * len(data_dict))
    values = tuple(data_dict.values())

    cursor.execute(f'INSERT INTO "{topic}" ({columns}) VALUES ({placeholders})', values)

    # Batch commit
    insert_counter += 1
    if insert_counter >= COMMIT_INTERVAL:
        conn.commit()
        insert_counter = 0


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
        cursor.execute(
            f"""
            CREATE TRIGGER "{trigger_name}"
            AFTER INSERT ON "{table_name}"
            WHEN (SELECT COUNT(*) FROM "{table_name}") > {max_rows}
            BEGIN
                DELETE FROM "{table_name}"
                WHERE rowid = (SELECT MIN(rowid) FROM "{table_name}");
            END;
        """
        )
        conn.commit()

        # immediately trim table if it exceeds the new limit
        cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        current_count = cursor.fetchone()[0]

        if current_count > max_rows:
            rows_to_delete = current_count - max_rows
            cursor.execute(
                f"""
                DELETE FROM "{table_name}"
                WHERE rowid IN (
                    SELECT rowid FROM "{table_name}"
                    ORDER BY rowid ASC
                    LIMIT {rows_to_delete}
                )
            """
            )
            conn.commit()


# ---------- Helper Functions ----------
def can_to_db_callback(
    system_info, cursor, conn, max_rows, topic_prefix: str, verbose: bool = True
):
    """Create a callback that bridges CAN messages to SQLite."""

    def callback(system_name: str, device_name: str, port: object, data: dict):
        dtype = get_device_type(system_info, device_name)
        topic_base = f"{topic_prefix}.{system_name}.{dtype}.{device_name}.transmit.{port.name}".lower()
        flt_dct = flatten_dict(data)

        payload = {"utc": int(time.time() * 1000)}

        if len(flt_dct) == 1:  # atomic data case
            topic = topic_base

        elif all_bools(flt_dct):  # all bools case 
            topic = topic_base
            flt_dct = {k: str(v) for k, v in flt_dct.items()} # convert bools to "True"/"False" strings for SQL

        else: # composite data entry - multiple values of mixed types
            pass # TODO: implement handling of composite data entries
        
        payload.update(flt_dct)
        insert_data(cursor, conn, topic, payload)

        if verbose:
            print(f"[CAN→DB] Published: {topic} -> {payload}")

    return callback


def start_can_receiver(
    system_info,
    cursor,
    conn,
    max_rows,
    topic_prefix: str = DEFAULT_MQTT_TOPIC_PREFIX,
    verbose: bool = True,
):
    """Start listening to CAN messages and forwarding them to DB."""
    receiver = CanReceiver(
        system_info,
        can_to_db_callback(system_info, cursor, conn, max_rows, topic_prefix, verbose),
    )
    receiver.run()


# ---------- Start CAN Receiver & Database ----------
def start_gateway(
    max_rows=MAX_ROWS_PER_TABLE,
    clear_db=True,
    topic_prefix=DEFAULT_MQTT_TOPIC_PREFIX,
    verbose=False,
):
    """
    Start the CAN→DB gateway.
    :param max_rows: max no. data entries per table
    :param clear_db: clear db before starting can receiver (default = true)
    :param verbose: Print DB inserts to console
    """

    conn, cursor = setup_database(clear=clear_db)

    # generate tables in SQLite db if they don't already exist
    compose_dict = load_composed_system_dict()
    openmct_dict = build_openmct_dict(compose_dict)
    create_all_tables(cursor, conn, openmct_dict, max_rows)

    # ensure triggers are updated in the event max_rows is changed via cli
    if not clear_db:
        update_max_rows_per_table(cursor, conn, max_rows)

    compose_result = get_compose_result_from_env()
    if not compose_result or not compose_result.success:
        raise RuntimeError(f"Failed to compose system: {compose_result.errors}")
    system_info = compose_result.system

    """Start listening to CAN messages and forwarding them to DB."""
    start_can_receiver(system_info, cursor, conn, max_rows, topic_prefix, verbose)


# ---------- Command-Line Interface ----------


def start_gateway_cli():
    parser = argparse.ArgumentParser(
        description="Starts a CAN to DB gateway that listens for CAN messages and inserts them into SQLite.\n "
        "The file path to the system info (.yaml files) needs to be provided via environment variables.\n "
        "NOVA_CAN_INTERFACES_PATH and NOVA_CAN_SYSTEMS_PATH"
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print DB inserts to console"
    )
    parser.add_argument(
        "-m",
        "--max-rows",
        type=int,
        default=MAX_ROWS_PER_TABLE,
        help="Maximum number of rows to keep per table",
    )
    parser.add_argument(
        "-t",
        "--topic-prefix",
        type=str,
        default=DEFAULT_MQTT_TOPIC_PREFIX,
        help="MQTT topic prefix",
    )
    parser.add_argument(
        "-c",
        "--clear-db",
        action="store_true",
        help="Clear the database before inserting CAN data",
    )

    args = parser.parse_args()
    start_gateway(
        max_rows=args.max_rows,
        clear_db=args.clear_db,
        topic_prefix=args.topic_prefix,
        verbose=args.verbose,
    )


# ---------- Default Usage ----------
if __name__ == "__main__":
    start_gateway_cli()
