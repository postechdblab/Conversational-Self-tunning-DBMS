from difflib import SequenceMatcher
import json
import itertools


def str_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def read_json(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data


file_path = "ratsql/datasets/augmentation/schema.txt"


data = read_json(file_path)

# collect mentions
mentions = []
for table in data["tables"]:
    tname = table["name"]
    tmentions = table["mentions"]
    for tmention in tmentions:
        mentions.append((f"{tname}", tmention))

    for col in table["columns"]:
        cname = col["name"]
        cmentions = col["mentions"]
        for cmention in cmentions:
            mentions.append((f"{tname} | {cname}", cmention))

# calculate similarities
candidates = []
threshold = 1
for (tc1, mention1), (tc2, mention2) in itertools.combinations(mentions, 2):
    score = str_similarity(mention1, mention2)
    if score >= threshold:
        if " | " in tc1 and " | " in tc2:
            if tc1.split(" | ")[1] == tc2.split(" | ")[1]:
                continue
        candidates.append(((tc1, mention1), (tc2, mention2)))

for (tc1, mention1), (tc2, mention2) in candidates:
    print(f'{tc1}:\t{mention1}')
    print(f'{tc2}:\t{mention2}')
    print()
