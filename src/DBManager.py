import mysql.connector
import secrets
import time
import HashManager
from contextlib import contextmanager

db_pool = None
def block_until_connected():
    global db_pool
    while True:
        try:
            temp_connection = mysql.connector.connect(
                host="mysql",
                user="root",
                password="toor" #Hardcoded for now
            )
            if(temp_connection.is_connected()):
                temp_cursor = temp_connection.cursor()
                temp_cursor.execute("CREATE DATABASE IF NOT EXISTS chatsql")
                temp_cursor.execute("USE chatsql")
                print("Connected to MySQL database")
                temp_cursor.close()
                temp_connection.close()

                db_pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="chatsql",
                    pool_size=5,
                    host="mysql",
                    user="root",
                    password="toor",
                    database="chatsql"
                )
                break
        except mysql.connector.Error:
            print("Waiting for database")
            time.sleep(1)

def get_db_connection(): #Had to implement a pool because of deadlocks, because Flask does some stuff asynchronously
    global db_pool
    return db_pool.get_connection()

@contextmanager
def get_db_cursor(commit=False): #This should hopefully be safe.
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        yield cursor
        if commit:
            connection.commit()
    finally:
        cursor.close()
        connection.close()

def rebuild_if_not_initialized():
    with get_db_cursor(commit=True) as cursor:
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

def is_auth_token_valid(auth_token, username):
    with get_db_cursor() as cursor:
        cursor.execute("""
        SELECT 1 FROM Sessions s
        INNER JOIN Users u ON s.user_id = u.user_id
        WHERE s.auth_token_hash = %s
        AND u.username = %s
        AND s.expiry_date > NOW()
        """, (HashManager.hash_auth_token(auth_token), username))

        valid = cursor.fetchone() is not None
        if not valid: #Remove expired tokens from database, to not clutter the table
            invalidate_auth_token(auth_token, username)
        return valid

def invalidate_auth_token(auth_token, username):
    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
        DELETE s FROM Sessions s
        INNER JOIN Users u ON s.user_id = u.user_id
        WHERE u.username = %s AND s.auth_token_hash = %s
        """, (username, HashManager.hash_auth_token(auth_token)))

def login(username, password):
    with get_db_cursor(commit=True) as cursor:
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
            return True, auth_token
        else:
            return False, None

def signup(username, email, password):
    user_already_exists = True
    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
        SELECT 1 FROM Users
        WHERE username = %s
        """, (username,))
        user = cursor.fetchone()
        
        if user is None: #If account with signup username does not exist, its valid, since we need unique usernames
            cursor.execute("""
            INSERT INTO Users (username, email, password_hash) VALUES (%s,%s,%s)
            """, (username, email, HashManager.hash_password(password)))
            user_already_exists = False
    if user_already_exists: 
        return False, None
    else:
        return login(username, password)#We need to keep this outside the with-block so our INSERT can be commited
