import DBManager
import random
import time

# https://github.com/pgcorpus/gutenberg/
def predict_next_words(query):
    max_num_sentences = 40
    split_row_chance = 40
    current_num_sentences = 0
    new_sentence = " " + query
    hit_dot = False
    while True:
        if hit_dot == True:
            break
        word = DBManager.predict_next_word(new_sentence.split(" ")[-1])
        if word is None:
            continue
        word = word.strip()
        if word.endswith("."):
            current_num_sentences += 1
            if random.randint(1,100) < split_row_chance:
                word += "<br>"
            if random.randint(1,max_num_sentences) < current_num_sentences:
                hit_dot = True
        new_sentence += " " + word
        yield f"data: {' ' + word}\n\n"
    yield "data: [DONE]\n\n"

def train_if_not_initialized():
    if DBManager.is_word_data_initialized():
        return
    
    grouped_dictionary = {}

    #Start "training" by reading sentences.txt and organizing them into word pairs.
    #Group them together based on the first word, what i call a "KeyWord"
    with open("sentences.txt", "r") as file:
        for i, line in enumerate(file):
            if i % 1000 == 0:
                print(f"{i} processed")
            line = line.strip()
            words = line.split(" ")
            if len(words) < 2:
                continue

            for j in range(len(words) - 1):
                first_word = words[j]
                second_word = words[j+1]
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
    for keyword, word_dict in grouped_dictionary.items():
        #print(f"{i}/{total} finalized")
        i += 1
        word_items = list(word_dict.items())
        word_items.sort(key=lambda x: x[0]) #sort by the word

        total_weight = 0
        for _, count in word_items:
            total_weight += count
        
        cumulative_weight = 0
        for word, count in word_items:
            cumulative_weight += count
            trained_rows.append((keyword, word, count, cumulative_weight, total_weight))

    print("Total rows:", len(trained_rows))
    print("Unique pairs:", len(set((r[0], r[1]) for r in trained_rows)))
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
    
