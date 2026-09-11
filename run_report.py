#!/usr/bin/env python3
"""Run a SQL report against the MSSQL invoice DB (zero-paper).

Run this LOCALLY -- on a machine/network that can reach the SQL Server on port
1433. (It will NOT work from a Claude Code web sandbox, whose egress is limited
to HTTP/HTTPS; the connection to 1433 times out there.)

It reads a .sql file, executes it, prints the result, and writes a .csv next to
it with the same base name. Pass the file to run; defaults to the cost-analysis
report when no argument is given.

  python run_report.py                                 # cost_analysis_april_2026.sql
  python run_report.py new_branches_last_two_weeks.sql # new branches, last 14 days

  1. Edit the `params` block at the top of the .sql file you are running.
  2. Set connection details via environment variables (see below).
  3. python run_report.py [report.sql]

Only the FIRST result set is captured, so keep one active SELECT per file (the
discovery queries in each report's SECTION 0 stay commented out for that reason).

Connection settings (environment variables):
  MSSQL_HOST       default: zero-paper.com
  MSSQL_PORT       default: 1433
  MSSQL_DB         REQUIRED -- the database/catalog name
  MSSQL_USER       default: readonlyuser
  MSSQL_PASSWORD   required (prompted if unset)
  MSSQL_DRIVER     default: 'ODBC Driver 18 for SQL Server'
  MSSQL_ENCRYPT    default: yes
  MSSQL_TRUST_CERT default: yes   (TrustServerCertificate)

One-time local prerequisites:
  pip install pyodbc
  + Microsoft ODBC Driver 18 for SQL Server:
      macOS:   brew install msodbcsql18
      Debian:  see Microsoft's apt repo (packages.microsoft.com)
      Windows: install the MSI from Microsoft
  Check installed drivers with:  python -c "import pyodbc; print(pyodbc.drivers())"
"""
import csv
import os
import sys
from getpass import getpass

try:
    import pyodbc
except ImportError:
    sys.exit("pyodbc is not installed. Run:  pip install pyodbc")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SQL = "cost_analysis_april_2026.sql"


def resolve_sql_path(argv):
    """Return the .sql file to run: argv[1] if given, else the default report."""
    if len(argv) > 2:
        sys.exit(f"Usage: {os.path.basename(argv[0])} [report.sql]")
    name = argv[1] if len(argv) == 2 else DEFAULT_SQL
    path = name if os.path.isabs(name) else os.path.join(HERE, name)
    if not os.path.exists(path):
        sys.exit(f"No such SQL file: {path}")
    return path


def build_conn_str():
    db = os.environ.get("MSSQL_DB")
    if not db:
        sys.exit("Set MSSQL_DB to the database name, e.g.  export MSSQL_DB=invoices")
    host = os.environ.get("MSSQL_HOST", "zero-paper.com")
    port = os.environ.get("MSSQL_PORT", "1433")
    user = os.environ.get("MSSQL_USER", "readonlyuser")
    pwd = os.environ.get("MSSQL_PASSWORD") or getpass(f"Password for {user}: ")
    driver = os.environ.get("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")
    encrypt = os.environ.get("MSSQL_ENCRYPT", "yes")
    trust = os.environ.get("MSSQL_TRUST_CERT", "yes")
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={db};"
        f"UID={user};"
        f"PWD={pwd};"
        f"Encrypt={encrypt};"
        f"TrustServerCertificate={trust};"
    )


def main():
    sql_file = resolve_sql_path(sys.argv)
    csv_out = os.path.splitext(sql_file)[0] + ".csv"

    with open(sql_file, "r", encoding="utf-8") as fh:
        query = fh.read()

    try:
        conn = pyodbc.connect(build_conn_str(), timeout=15)
    except pyodbc.Error as e:
        sys.exit(f"Connection failed: {e}")

    with conn:
        cur = conn.cursor()
        cur.execute(query)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()

    with open(csv_out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(list(r))

    print("\t".join(cols))
    for r in rows:
        print("\t".join("" if v is None else str(v) for v in r))
    print(f"\n{len(rows)} row(s). CSV written to {csv_out}")


if __name__ == "__main__":
    main()
