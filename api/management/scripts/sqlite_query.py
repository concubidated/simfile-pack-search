import sqlite3

def fetch_song_chart_data(db_path):
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data, fullsize, filename from SONGS")
            return cursor.fetchall()
    except Exception as e:
        print(f"Error: {e}")

