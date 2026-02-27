import mysql.connector
import secrets
import time
import HashManager

connection = None
cursor = None
def block_until_connected():
    global connection 
    global cursor #Not the best practice, but it works for this enclosed module
    while True:
        try:
            connection = mysql.connector.connect(
                host="mysql",
                user="root",
                password="toor", #Hardcoded for now
            )
            if(connection.is_connected()):
                cursor = connection.cursor()
                cursor.execute("CREATE DATABASE IF NOT EXISTS chatsql")
                cursor.execute("USE chatsql")
                print("Connected to MySQL database")
                break
        except mysql.connector.Error:
            print("Waiting for database")
            time.sleep(1)
    #cursor.execute("SELECT * FROM Users")
    #print(cursor.fetchall())
    #cursor.execute("DELETE FROM Users")
    #connection.commit()


def rebuild_if_not_initialized():
    global cursor
    global connection

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        user_id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(20) NOT NULL UNIQUE,
        email VARCHAR(254) NOT NULL,
        password_hash VARCHAR(60) NOT NULL
    )
    """)

    #For a "real" application it should store IP, Login date, etc. for logs and to prevent fraud
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Sessions (
        user_id INT NOT NULL,
        auth_token_hash VARCHAR(64) NOT NULL,
        expiry_date DATE NOT NULL,
        FOREIGN KEY (user_id) REFERENCES Users(user_id),
        PRIMARY KEY (user_id, auth_token_hash)
    )
    """)
    connection.commit()

def is_auth_token_valid(auth_token, username):
    global cursor
    cursor.execute("""
    SELECT 1 FROM Sessions s
    INNER JOIN Users u ON s.user_id = u.user_id
    WHERE s.auth_token_hash = %s
    AND u.username = %s
    AND s.expiry_date > NOW()
    """, (HashManager.hash_auth_token(auth_token), username))
    return cursor.fetchone() is not None 

def login(username, password):
    global cursor
    global connection
    print(username)
    print(password)
    cursor.execute("""
    SELECT password_hash FROM Users
    WHERE username = %s
    """, (username,))
    password_hash = cursor.fetchone()
    if password_hash and HashManager.verify_hashed_password(password, password_hash[0]):
        auth_token = secrets.token_hex(32) #32 bytes, but 64 hex characters long

        #I chose to use DATE_ADD so we get consistent dates, since we used NOW() above where we check the auth_token
        cursor.execute("""
        INSERT INTO Sessions (user_id, auth_token_hash, expiry_date) VALUES
        (
            (SELECT user_id FROM Users WHERE username = %s), 
            %s, 
            DATE_ADD(NOW(), INTERVAL 24 HOUR)
        )
        """, (username, HashManager.hash_auth_token(auth_token)))

        connection.commit()
        return True, auth_token
    else:
        return False, None

def signup(username, email, password):
    global cursor
    global connection
    cursor.execute("""
    SELECT 1 FROM Users
    WHERE username = %s
    """, (username,))
    
    if cursor.fetchone() is None: #If account with signup username does not exist, its valid, since we need unique usernames
        cursor.execute("""
        INSERT INTO Users (username, email, password_hash) VALUES (%s,%s,%s)
        """, (username, email, HashManager.hash_password(password)))
        connection.commit()
        return login(username, password)
    else:
        return False, None
