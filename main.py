import mariadb
import random
import time
import re
from pyarrow.parquet import ParquetFile
import pyarrow
import sys
invalidChars = ["<unk>", "  ", "= = =", "= = "]


def cleanLine(line):
    if line.startswith(" "):
        line = line[1:]
    #for char in invalidChars:
    #    line = line.replace(char, "")
    #line = re.sub(r'[^a-zA-Z0-9\s.,!?]', '', line).lower()
    return line

def overwriteUnaryDataset(cursor, conn):
    cursor.execute("DROP TABLE IF EXISTS UnaryDataset")
    cursor.execute(
        """
        CREATE TABLE UnaryDataset (
            KeyToken TEXT NOT NULL,
            NextToken TEXT NOT NULL,
            Num INTEGER NOT NULL DEFAULT 1
        );
        """)
    with open("wikidata.txt", "r") as file:
        lines = file.readlines()
        total = len(lines)
        index = 0
        for line in lines:
            if index % 100 == 0:
                print(f"Progress: {index}/{total}")
            index += 1
            words = cleanLine(line).split(" ")
            if len(words) < 2: 
                continue
            for word in words:
                if word == "":
                    words.remove(word)
            for i in range(0,len(words)-2):
                word = words[i]
                nextWord = words[i+1]
                cursor.execute(
                    """
                    INSERT INTO UnaryDataset (KeyToken, NextToken) 
                    VALUES (?, ?)
                    ON DUPLICATE KEY UPDATE Num = Num + 1;
                    """, (word, nextWord))

    conn.commit()

def predictNextWord(cursor, conn, string):
    lastWord = string.split(" ")[-1]
    cursor.execute("SELECT SUM(Num) FROM UnaryDataset WHERE KeyToken = ?", (lastWord,))    
    total = cursor.fetchone()[0]
    if total == None: return string
    total = int(total)
    
    cursor.execute("SELECT * FROM UnaryDataset WHERE KeyToken = ?", (lastWord,))
    cumWeightTable = []
    cumWeight = 0
    for row in cursor:
        cumWeight += row[2]
        cumWeightTable.append((row[0],row[1],cumWeight))
    cumWeightTableSorted = sorted(cumWeightTable, key=lambda x: x[2])
    value = random.randint(1, total)
    for row in cumWeightTableSorted:
        if row[2] > value:
            return string + " " + row[1]
    return string
try:
    conn = mariadb.connect(
        user="root",
        password="toor",
        host="127.0.0.1",
        port=4000
    )
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS DB")
    cursor.execute("USE DB")
    conn.commit()

    #overwriteUnaryDataset(cursor, conn)
    #with open("wikidata.txt", "w") as f:
    #    file = ParquetFile("train-00000-of-00001.parquet")
    #    for batch in file.iter_batches(batch_size=1000, columns=['text']):
    #        df = batch.to_pandas()
    #        for _, row in df.iterrows():
    #            f.write(row['text'])
        


    #sys.exit()
    print("\n")
    #cursor.execute("SELECT * FROM UnaryDataset ORDER BY RAND() LIMIT 1")
    #completeString = cursor.fetchone()[0]
    completeString = "I am such a piece"
    lastString = ""
    while True:
        completeString = predictNextWord(cursor, conn, completeString)
        if completeString.endswith("."):
            cursor.execute("SELECT * FROM UnaryDataset ORDER BY RAND() LIMIT 1")
            completeString += " " + cursor.fetchone()[0]
        elif completeString == lastString:
            completeString += "."
            #break
        lastString = completeString
        print(completeString.split(" ")[-1], end=" ", flush=True)
            
    print("\n")

    cursor.close()
    conn.close()

except mariadb.Error as e:
    print(e)
