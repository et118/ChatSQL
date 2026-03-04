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
                temp_cursor.execute("SET GLOBAL innodb_buffer_pool_size = 4000000000")
                print("Connected to MySQL database")
                temp_cursor.close()
                temp_connection.close()

                db_pool = mysql.connector.pooling.MySQLConnectionPool(
                    pool_name="chatsql",
                    pool_size=10,
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

        #Creating the bot user. Ignore if already exists
        cursor.execute("""
        INSERT IGNORE INTO Users (user_id, username, email, password_hash)
        VALUES (1, 'ChatSQL', '', '')
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

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Chats (
            chat_id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            user_id INT NOT NULL,
            creation_date DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES Users(user_id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Message (
            message_id INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
            chat_id INT NOT NULL,
            sender_id INT NOT NULL,
            message TEXT NOT NULL,
            creation_date DATETIME NOT NULL,
            FOREIGN KEY (sender_id) REFERENCES Users(user_id),
            FOREIGN KEY (chat_id) REFERENCES Chats(chat_id)
        )
        """)

        #Creating my own DROP INDEX IF NOT EXISTS because apparently it doesnt work in mysql
        #Credit to https://overflow.adminforge.de/questions/39849002/how-to-make-drop-index-if-exists-for-mysql
        cursor.execute("DROP PROCEDURE IF EXISTS drop_index_if_exists;")
        cursor.execute("""
        CREATE PROCEDURE drop_index_if_exists(IN tab_name VARCHAR(64), IN ind_name VARCHAR(64))
        BEGIN
            SET @tableName = tab_name;
            SET @indexName = ind_name;
            SET @indexExists = 0;
            
            SELECT 1 INTO @indexExists
            FROM information_schema.statistics
            WHERE TABLE_NAME = @tableName
            AND INDEX_NAME = @indexName;

            SET @query = CONCAT('DROP INDEX ', @indexName, ' ON ', @tableName);
            IF @indexExists THEN
                PREPARE stmt FROM @query;
                EXECUTE stmt;
                DEALLOCATE PREPARE stmt;
            END IF;
        END;
        """)

        #The function used to query the next word. i had to add BINARY to make the word comparison include capitalized characters
        cursor.execute("DROP FUNCTION IF EXISTS get_next_word;")
        cursor.execute("""
        CREATE FUNCTION get_next_word(input_word VARCHAR(64)) RETURNS VARCHAR(64)
        DETERMINISTIC
        BEGIN
            DECLARE random_weight INT;
            DECLARE output_word VARCHAR(64);
            
            SELECT FLOOR(RAND() * total_weight)
                INTO random_weight
                FROM WordData
                WHERE keyword = BINARY input_word
                LIMIT 1;

            IF random_weight IS NULL THEN
                SELECT predict_word
                    INTO output_word
                    FROM WordData
                    ORDER BY RAND()
                    LIMIT 1;
            ELSE
                SELECT predict_word
                    INTO output_word
                    FROM WordData
                    WHERE keyword = BINARY input_word
                    AND cumulative_weight >= random_weight
                    ORDER BY cumulative_weight ASC
                    LIMIT 1;
            END IF;
            RETURN output_word;
        END;
        """)

        #cursor.execute("SELECT user_id FROM Users WHERE user_id = 3")
        #print(cursor.fetchall())

def is_word_data_initialized():
    with get_db_cursor() as cursor:
        cursor.execute("""SHOW TABLES LIKE %s""", ("WordData",))
        return cursor.fetchone() is not None

def clear_word_data_table():
    with get_db_cursor(commit=True) as cursor:
        cursor.execute("CALL drop_index_if_exists('WordData', 'index_keyword_cumulative_weight')")
        cursor.execute("DROP TABLE IF EXISTS WordData")

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS WordData (
            keyword VARCHAR(255) NOT NULL,
            predict_word VARCHAR(255) NOT NULL,
            count INT NOT NULL,
            cumulative_weight INT NOT NULL,
            total_weight INT NOT NULL,
            PRIMARY KEY (keyword, predict_word)
        );""")

        cursor.execute("""
        CREATE INDEX index_keyword_cumulative_weight ON WordData(keyword, cumulative_weight);
        """)#We use an index to order the items for faster querying, since its a cumulative weight for choosing a specific word
        
def add_word_data_rows(rows):
    with get_db_cursor(commit=True) as cursor:
        #i dont know why, but i had to add IGNORE because it said some of the input data was duplicated
        #but it really wasnt. I checked in numerous ways, so i decided to just ignore if something goes wrong.
        #at most we lose a couple words.
        cursor.executemany("""
        INSERT IGNORE INTO WordData (keyword, predict_word, count, cumulative_weight, total_weight) 
        VALUES (%s, %s, %s, %s, %s)
        """, rows)

def predict_next_word(word):
    with get_db_cursor() as cursor:
        cursor.execute("SELECT get_next_word(%s) LIMIT 1", (word,))
        return cursor.fetchone()[0]

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

def create_new_chat(auth_token):
    with get_db_cursor(commit=True) as cursor:
        cursor.execute("""
        INSERT INTO Chats (user_id, creation_date)
        SELECT u.user_id, NOW() FROM Users u
        INNER JOIN Sessions s ON u.user_id = s.user_id
        WHERE %s = s.auth_token_hash
        """, (HashManager.hash_auth_token(auth_token),))
        return cursor.lastrowid

def create_new_message(chat_id, message, auth_token): #Missing auth_token means it was the bot who sent it
    with get_db_cursor(commit=True) as cursor:
        sender_id = 1
        if auth_token != "":
            cursor.execute("""
            SELECT user_id FROM Sessions WHERE auth_token_hash = %s
            """, (HashManager.hash_auth_token(auth_token),))
            sender_id = cursor.fetchone()[0]
        cursor.execute("""
        INSERT INTO Message (chat_id, sender_id, message, creation_date)
        VALUES (%s, %s, %s, NOW())
        """, (chat_id, sender_id, message))

def get_chat_history(chat_id, auth_token):
    with get_db_cursor() as cursor:
        cursor.execute("""
        SELECT m.sender_id, m.message FROM Message m 
        INNER JOIN Chats c ON m.chat_id = c.chat_id
        INNER JOIN Users u ON c.user_id = u.user_id
        INNER JOIN Sessions s ON s.user_id = u.user_id
        WHERE s.auth_token_hash = %s
        AND m.chat_id = %s
        ORDER BY m.creation_date ASC
        """, (HashManager.hash_auth_token(auth_token), chat_id))

        return cursor.fetchall()

def get_chats(auth_token):
    with get_db_cursor() as cursor:
        cursor.execute("""
        SELECT chat_id FROM Chats c
        INNER JOIN Sessions s ON c.user_id = s.user_id
        WHERE s.auth_token_hash = %s
        ORDER BY c.creation_date DESC
        """, (HashManager.hash_auth_token(auth_token),))
        return cursor.fetchall()

def get_word_database_stats():
    with get_db_cursor() as cursor:
        cursor.execute("""
        SELECT keyword, COUNT(*) FROM WordData
        GROUP BY keyword
        HAVING COUNT(*) > 10
        ORDER BY COUNT(*) DESC
        """)

        return cursor.fetchall()

def get_word_stats(word):
    with get_db_cursor() as cursor:
        cursor.execute("""
        SELECT * FROM WordData
        WHERE keyword = BINARY %s
        ORDER BY cumulative_weight
        """, (word,))

        return cursor.fetchall()

def get_user_stats():
    with get_db_cursor() as cursor:
        cursor.execute("""
        SELECT * FROM Users
        """)

        users = cursor.fetchall()

        cursor.execute("""
        SELECT u.username, s.auth_token_hash, s.expiry_date FROM Sessions s
        INNER JOIN Users u ON s.user_id = u.user_id
        """)

        sessions = cursor.fetchall()

        return users, sessions
