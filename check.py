import sqlite3; conn = sqlite3.connect('zenith.db'); print(conn.execute('SELECT name FROM sqlite_master WHERE type=%stable%s' % (chr(39),chr(39))).fetchall())
