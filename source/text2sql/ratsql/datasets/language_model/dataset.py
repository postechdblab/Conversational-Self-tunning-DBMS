import random
import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader

def pad_sequence_for_bert_batch(tokens_lists):
    pad_id = 1 # tokenizer.pad_token_id
    sep_id = 2 # tokenizer.sep_token_id
    max_len = max([len(it) for it in tokens_lists])
    toks_ids = []
    att_masks = []
    tok_type_lists = []
    for item_toks in tokens_lists:
        padded_item_toks = item_toks + [pad_id] * (max_len - len(item_toks))
        toks_ids.append(padded_item_toks)

        _att_mask = [1] * len(item_toks) + [0] * (max_len - len(item_toks))
        att_masks.append(_att_mask)

        first_sep_id = padded_item_toks.index(sep_id)
        assert first_sep_id > 0
        _tok_type_list = [0] * (first_sep_id + 1) + [1] * (max_len - first_sep_id - 1)
        tok_type_lists.append(_tok_type_list)
    return toks_ids, att_masks, tok_type_lists

def data_collate_fn(dataset_samples_list):
    # String to idx
    input_ids = []
    attention_masks = []
    golds = []
    for input_info, gold in dataset_samples_list:
        input_ids.append(input_info['input_ids'])
        # attention_masks.append(input_info['attention_mask'])
        golds.append(gold)

    toks_ids, att_masks, tok_type_lists = pad_sequence_for_bert_batch(input_ids)
    return toks_ids, att_masks, tok_type_lists, golds


class PLMDataset(Dataset):
    def __init__(self, path, tokenizer):
        self.path = path
        self.tokenizer = tokenizer
        self.__load_data(path)

    def __load_data(self, path):
        self.words = []
        self.acrons = []
        self.descs = []
        with open(path, "r") as f:
            for idx, line in enumerate(f):
                if idx == 0:
                    continue
                line_s = line.split('\t')
                if len(line_s) != 3:
                    continue
                word, acron, desc = line_s
                self.words.append(word)
                self.acrons.append(acron)
                self.descs.append(desc)

    def __len__(self):
        return len(self.words)

    def __random_idx(self, except_num):
        rand_idx = except_num
        while rand_idx == except_num:
            rand_idx = random.randint(0, len(self.words))
        return rand_idx

    def __getitem__(self, idx):
        # Task setting
        task_idx = 1 if random.randint(0,1) else 2
        gold = random.randint(0,1)
        # Idx setting
        word_idx = idx
        arcon_idx = desc_idx = word_idx if gold else self.__random_idx(word_idx)
        # Input setting
        if task_idx == 1:
            input_string = f"{self.words[word_idx]} [SEP] {self.acrons[arcon_idx]}"
        else:
            input_string = f"{self.words[word_idx]} [SEP] {self.descs[desc_idx]}"
        input_token_ids = self.tokenizer(input_string)
        
        return (input_token_ids, gold)