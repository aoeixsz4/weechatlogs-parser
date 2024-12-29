import os
import re
import sqlite3
import argparse


# Database initialization function
def initialize_database(db_name):
    """
    Initialize the SQLite database and create necessary tables.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            network TEXT,
            channel TEXT,
            timestamp TEXT,
            log_type TEXT,
            nick TEXT,
            message TEXT
        )
    """
    )
    conn.commit()
    conn.close()


# Parse each file (generator)
def parse_weechat_logfile(file):
    with open(file, "r") as f:
        for line in f:
            line = line.strip("\n")
            timestamp, mid, rest = line.split("\t", maxsplit=2)
            if mid == " *":
                # ACTION
                try:
                    nick, rest = rest.split(" ", maxsplit=1)
                except ValueError:
                    nick, rest = rest, ""
                yield timestamp, "ACTION", nick, rest
            elif mid == "--":
                yield timestamp, "SERVER INFO", "", rest
            elif mid == "":
                yield timestamp, "CLIENT INFO", "", rest
            elif mid == "-->":
                nick, rest = rest.split(" ", maxsplit=1)
                yield timestamp, "JOIN", nick, rest
            elif mid == "<--":
                nick, rest = rest.split(" ", maxsplit=1)
                yield timestamp, "PART", nick, rest
            else:
                nick, message = mid, rest
                yield timestamp, "MESSAGE", nick, message


# Function to parse WeeChat logs
def parse_weechat_logs(log_directory, db_name):
    """
    Parse WeeChat logs from the specified directory and store them in the database.

    Args:
        log_directory (str): Directory containing WeeChat logs.
        db_name (str): SQLite database file to store parsed logs.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    for file in os.listdir(log_directory):
        parts = file.split(".")
        irc = parts[0]
        network = parts[1]
        ext = parts[-1]
        if irc != "irc" or network == "server" or ext != "weechatlog":
            continue
        channel = ".".join(parts[2:-1])
        for timestamp, log_type, nick, message in parse_weechat_logfile(
            os.path.join(log_directory, file)
        ):
            if log_type not in {"ACTION", "MESSAGE"}:
                continue
            nick = nick.strip("+@%")
            cursor.execute(
                """
                INSERT INTO logs (network, channel, timestamp, log_type, nick, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (network, channel, timestamp, log_type, nick, message),
            )
            # print(
            #     f"INSERT INTO logs (network, channel, timestamp, log_type, nick, message), {network, channel, timestamp, log_type, nick, message}"
            # )

    conn.commit()
    conn.close()


# Function to search logs
def search_logs(db_name, query=None, channel=None, nick=None, log_type=None, date=None):
    """
    Search logs in the database for a given query.

    Args:
        db_name (str): SQLite database file.
        query (str): Search query.
        channel (str): Optional channel name to narrow the search.
        log_type (str): Optional log type filter (ACTION or MESSAGE).

    Returns:
        list: Matching log entries.
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    query_conditions = []
    query_params = []

    if query:
        query_conditions.append("message LIKE ?")
        query_params.append(f"%{query}%")

    if channel:
        query_conditions.append("channel = ?")
        query_params.append(channel)

    if nick:
        query_conditions.append("nick = ?")
        query_params.append(nick)

    if log_type:
        query_conditions.append("log_type = ?")
        query_params.append(log_type.upper())

    if date:
        query_conditions.append("timestamp LIKE ?")
        query_params.append(f"%{date}%")

    sql_query = f"""
        SELECT timestamp, nick, message, channel, log_type
        FROM logs
        WHERE {" AND ".join(query_conditions)}
        ORDER BY timestamp ASC
    """

    cursor.execute(sql_query, query_params)
    results = cursor.fetchall()
    conn.close()
    return results


# Function to print logs
def print_logs(logs):
    """
    Print log entries in a readable format.
    """
    for timestamp, nick, message, channel, log_type in logs:
        print(f"[{timestamp}] {channel} ({log_type}) <{nick}>: {message}")


# CLI interface
def main():
    parser = argparse.ArgumentParser(
        description="WeeChat Log Parser and Query Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available commands"
    )

    # Initialize database
    init_parser = subparsers.add_parser("init", help="Initialize the SQLite database")
    init_parser.add_argument("--db", required=True, help="SQLite database file")

    # Parse logs
    parse_parser = subparsers.add_parser(
        "parse", help="Parse WeeChat logs and store them in the database"
    )
    parse_parser.add_argument(
        "--logs", required=True, help="Directory containing WeeChat logs"
    )
    parse_parser.add_argument("--db", required=True, help="SQLite database file")

    # Search logs
    search_parser = subparsers.add_parser("search", help="Search WeeChat logs")
    search_parser.add_argument("--db", required=True, help="SQLite database file")
    search_parser.add_argument("--query", help="Search query")
    search_parser.add_argument("--nick", help="Search nick")
    search_parser.add_argument("--channel", help="Optional channel to filter results")
    search_parser.add_argument("--date", help="Search date")
    search_parser.add_argument(
        "--type",
        choices=["ACTION", "MESSAGE"],
        help="Optional log type filter (ACTION or MESSAGE)",
    )

    # Execute CLI
    args = parser.parse_args()

    if args.command == "init":
        initialize_database(args.db)
        print(f"Database initialized: {args.db}")
    elif args.command == "parse":
        parse_weechat_logs(args.logs, args.db)
        print(f"WeeChat logs parsed and stored in: {args.db}")
    elif args.command == "search":
        results = search_logs(
            args.db, args.query, args.channel, args.nick, args.type, args.date
        )
        if results:
            print_logs(results)
        else:
            print("No matching logs found.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
