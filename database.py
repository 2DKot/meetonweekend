import sqlite3

conn = sqlite3.connect("polls.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS poll (
        dt_key TEXT NOT NULL,
        group_chat_id INTEGER NOT NULL,
        created_by INTEGER NOT NULL,
        created_at DATETIME NOT NULL,
        group_name TEXT NOT NULL,
        PRIMARY KEY (dt_key, group_chat_id)
    );
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_poll (
        user_id INTEGER NOT NULL,
        dt_key TEXT NOT NULL,
        group_chat_id INTEGER NOT NULL,
        sat_vote TEXT NOT NULL,
        sat_ready BOOLEAN DEFAULT FALSE,
        sun_vote TEXT NOT NULL,
        sun_ready BOOLEAN DEFAULT FALSE,
        PRIMARY KEY (user_id, dt_key, group_chat_id),
        FOREIGN KEY (dt_key, group_chat_id) REFERENCES poll(dt_key, group_chat_id)
    );
""")

conn.commit()
