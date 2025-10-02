import os
import json

if __name__ == "__main__":
    pass

file_path = "/data/hkkang/NL2QGM/ratsql/datasets/augmentation/schema.txt"
with open(file_path) as f:
    data = json.load(f)

values = []
for table in data['tables']:
    for column in table['columns']:
        values += column['values']
    

# Custom values
values += list(range(0,10))
values += [2018, 2019, 2020, 2021]
values += [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

out_path = "/data/hkkang/NL2QGM/data/spider-kor-cloud-postgres/spider-kor-colemb-addop/dec_vocab.json"
with open(out_path, 'r') as f:
    vocab = json.load(f)

vocab += values
vocab = list(set(vocab))

with open(out_path, 'w') as f:
    json.dump(vocab, f)
    