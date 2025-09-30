# Get schema length
class Schema():
    def __init__(self, info):
        self.db_name = info['db_name']
        self.tabs = info['table']
        self.cols = info['column']
        self.tokenizer = None

    def set_tokenizer(self, tokenizer):
        self.tokenizer = tokenizer

    def tokenize(self, sen):
        if self.tokenizer:
            return self.tokenizer(sen)
        else:
            return sen.split(" ")

    ## Element count
    def len(self, ele):
        return len(ele)

    def get_tab_len(self):
        return self.len(self.tabs)

    def get_col_len(self):
        return self.len(self.cols)

    def schema_len(self):
        return self.get_tab_len() + self.get_col_len()
    
    ## Token length
    def token_len(self, ele):
        if self.tokenizer:
            return len(self.tokenizer(ele))
        else:
            return ele.split(" ")

    def get_tab_tok_len(self):
        return sum([self.token_len(tab) for tab in self.tabs])

    def get_col_tok_len(self):
        return sum([self.token_len(col) for col in self.cols])

    def schema_tok_len(self):
        return self.get_tab_tok_len() + self.get_col_tok_len()