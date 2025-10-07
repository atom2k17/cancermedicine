# run.py - small CLI to run & init DB
import os
from app import create_app, db
from app.models import User, Medicine, Match

app = create_app()

@app.cli.command("db_create")
def db_create():
    db.create_all()
    print("Database created (SQLite).")

@app.cli.command("runserver")
def runserver():
    app.run(debug=True, host="127.0.0.1", port=5000)

if __name__ == "__main__":
    app.run(debug=True)