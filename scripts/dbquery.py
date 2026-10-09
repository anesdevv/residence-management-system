import argparse
import os
import sys

try:
    import psycopg
except ImportError:  # pragma: no cover
    print("psycopg is not installed in the interpreter running this script", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SQL verification queries against the hosted Supabase Postgres.")
    parser.add_argument("query", nargs="?", help="inline SQL statement(s)")
    parser.add_argument("--file", "-f", help="read SQL from a file")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            sql = fh.read()
    elif args.query:
        sql = args.query
    elif not sys.stdin.isatty():
        sql = sys.stdin.read()
    else:
        parser.error("provide a query argument, --file, or piped stdin")

    url = os.environ["SUPABASE_URL"]
    password = os.environ["SUPABASE_DB_PASSWORD"]
    ref = url.replace("https://", "").split(".")[0]

    conn = psycopg.connect(
        host=os.environ.get("SUPABASE_DB_HOST", "aws-0-eu-west-1.pooler.supabase.com"),
        port=5432,
        user=f"postgres.{ref}",
        password=password,
        dbname="postgres",
        connect_timeout=20,
        sslmode="require",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is not None:
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
                print("\t".join(cols))
                for row in rows:
                    print("\t".join("" if v is None else str(v) for v in row))
                print(f"({len(rows)} rows)")
            else:
                print(f"OK ({cur.rowcount} rows affected)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()