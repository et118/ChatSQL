import mariadb

try:
    conn = mariadb.connect(
        user="root",
        password="toor",
        host="127.0.0.1",
        port=4000
    )
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS data")
    cursor.execute("USE data")

    

    

    conn.commit()
    cursor.close()
    conn.close()
except mariadb.Error as e:
    print(e)
