#!/usr/bin/env python3
"""Run the April-2026 cost-analysis report against the MSSQL invoice DB.

Run this LOCALLY -- on a machine/network that can reach the SQL Server on port
1433. (It will NOT work from a Claude Code web sandbox, whose egress is limited
to HTTP/HTTPS; the connection to 1433 times out there.)

It reads the report query from cost_analysis_april_2026.sql, executes it, prints
the result, and writes cost_analysis_april_2026.csv.

  1. Edit the `params` block at the top of cost_analysis_april_2026.sql
     (set your master_account_id; adjust dates only if needed).
  2. Set connection details via environment variables (see below).
  3. python run_report.py

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
SQL_FILE = os.path.join(HERE, "cost_analysis_april_2026.sql")
CSV_OUT = os.path.join(HERE, "cost_analysis_april_2026.csv")


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
    with open(SQL_FILE, "r", encoding="utf-8") as fh:
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

    with open(CSV_OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(list(r))

    print("\t".join(cols))
    for r in rows:
        print("\t".join("" if v is None else str(v) for v in r))
    print(f"\n{len(rows)} row(s). CSV written to {CSV_OUT}")


if __name__ == "__main__":
    main()
