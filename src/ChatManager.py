import DBManager
import random
import time

# https://github.com/pgcorpus/gutenberg/
def predict_next_words(query, chat_id):
    max_num_sentences = 1
    split_row_chance = 40
    current_num_sentences = 0
    new_sentence = " " + query
    final_message = ""
    hit_dot = False
    while True:
        if hit_dot == True:
            break
        word = DBManager.predict_next_word(new_sentence.split(" ")[-1])
        if word is None:
            continue
        word = word.strip()
        breakline = ""
        if word.endswith("."):
            current_num_sentences += 1
            if random.randint(1,100) < split_row_chance:
                breakline = "<br>"
            if random.randint(1,max_num_sentences) < current_num_sentences:
                hit_dot = True
        new_sentence += " " + word
        final_message += ' ' + word + breakline
        yield f"data: {' ' + word + breakline}\n\n"
        time.sleep(0.01)
    DBManager.create_new_message(chat_id, final_message, "")
    yield "data: [DONE]\n\n"

def train_if_not_initialized():
    if DBManager.is_word_data_initialized():
        return
    
    grouped_dictionary = {}

    #Start "training" by reading sentences.txt and organizing them into word pairs.
    #Group them together based on the first word, what i call a "KeyWord"
    with open("sentences.txt", "r") as file:
        saved_word = ""
        for i, line in enumerate(file):
            if i % 1000 == 0:
                print(f"{i} processed")
            line = line.strip()
            words = line.split(" ")
            if len(words) < 2:
                continue

            minimum = 0
            if saved_word != "":
                minimum = -1
            for j in range(minimum, len(words) - 1):
                if j == -1:
                    first_word = saved_word
                    saved_word = ""
                else:
                    first_word = words[j]
                second_word = words[j+1]
                if j == len(words) - 2:
                    saved_word = second_word

                if first_word == "" or second_word == "":
                    continue
                
                if first_word not in grouped_dictionary:
                    grouped_dictionary[first_word] = {}
                
                if second_word not in grouped_dictionary[first_word]:
                    grouped_dictionary[first_word][second_word] = 0
                
                
                
                grouped_dictionary[first_word][second_word] += 1

    

    #And now calculating cumulative weight
    trained_rows = []
    i = 0
    total = len(grouped_dictionary.items())
    valid_keywords = set(grouped_dictionary.keys())
    for keyword, word_dict in grouped_dictionary.items():
        i += 1

        #Remove predictions that dont have a keyword, since they slow down the search a LOT by searching through entire database.
        filtered_items = []
        for word, count in word_dict.items():
            if word in valid_keywords:
                filtered_items.append((word, count))

        if len(filtered_items) == 0:
            continue

        filtered_items.sort(key=lambda x: x[0]) #sort by the word

        total_weight = 0
        for _, count in filtered_items:
            total_weight += count
        
        cumulative_weight = 0
        for word, count in filtered_items:
            cumulative_weight += count
            trained_rows.append((keyword, word, count, cumulative_weight, total_weight))

    print("Total rows:", len(trained_rows))
    print("Clearing word data table")
    DBManager.clear_word_data_table()
    print("Inserting new data")
    length = len(trained_rows)
    max_chunksize = 100000
    for i in range(0, length, max_chunksize):
        print(f"Chunk {int(i/max_chunksize)}/{int(length / max_chunksize)}")
        batch = trained_rows[i:i + max_chunksize]
        DBManager.add_word_data_rows(batch)
    print("All done")
    
