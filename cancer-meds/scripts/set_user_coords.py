"""
Simple helper to update user latitude/longitude in the project's SQLite DB.
Usage examples:
  python scripts\set_user_coords.py --id 3 --lat 12.34 --lon 56.78
  python scripts\set_user_coords.py --email user@example.com --lat 12.34 --lon 56.78
  python scripts\set_user_coords.py --csv users_coords.csv  # CSV: email,latitude,longitude (header optional)

This script talks directly to the `site.db` SQLite file in the project root.
"""
import argparse
import csv
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'site.db')


def update_by_id(conn, user_id, lat, lon):
    cur = conn.cursor()
    cur.execute("UPDATE user SET latitude = ?, longitude = ? WHERE id = ?", (lat, lon, user_id))
    conn.commit()
    return cur.rowcount


def update_by_email(conn, email, lat, lon):
    cur = conn.cursor()
    cur.execute("UPDATE user SET latitude = ?, longitude = ? WHERE email = ?", (lat, lon, email))
    conn.commit()
    return cur.rowcount


def process_csv(conn, csv_path):
    updated = 0
    with open(csv_path, newline='', encoding='utf-8') as fh:
        reader = csv.reader(fh)
        for row in reader:
            if not row:
                continue
            # accept either: email,lat,lon  OR id,lat,lon
            if len(row) < 3:
                print('Skipping malformed row:', row)
                continue
            key, lat_s, lon_s = row[0].strip(), row[1].strip(), row[2].strip()
            try:
                lat = float(lat_s)
                lon = float(lon_s)
            except ValueError:
                print('Skipping row with invalid coords:', row)
                continue
            if '@' in key:
                updated += update_by_email(conn, key, lat, lon)
            else:
                try:
                    uid = int(key)
                    updated += update_by_id(conn, uid, lat, lon)
                except ValueError:
                    print('Skipping row with unknown key:', row)
    return updated


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--id', type=int, help='User id to update')
    p.add_argument('--email', help='User email to update')
    p.add_argument('--lat', type=float, help='Latitude')
    p.add_argument('--lon', type=float, help='Longitude')
    p.add_argument('--csv', help='CSV file with rows email(or id),latitude,longitude')
    args = p.parse_args()

    if not os.path.exists(DB_PATH):
        print('Database not found at', DB_PATH)
        sys.exit(2)

    conn = sqlite3.connect(DB_PATH)
    try:
        if args.csv:
            changed = process_csv(conn, args.csv)
            print(f'Rows updated: {changed}')
            return

        if args.id and args.lat is not None and args.lon is not None:
            changed = update_by_id(conn, args.id, args.lat, args.lon)
            print(f'Rows updated: {changed}')
            return

        if args.email and args.lat is not None and args.lon is not None:
            changed = update_by_email(conn, args.email, args.lat, args.lon)
            print(f'Rows updated: {changed}')
            return

        print('Nothing to do. Provide --id or --email together with --lat and --lon, or --csv file')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
