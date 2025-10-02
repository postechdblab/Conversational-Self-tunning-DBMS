
class Acc:
    classify = ["rule", "token", "pointer"]
    def __init__(self):

        self.cnt_dict = dict()
        self.correct_dict = dict()

        for cl in Acc.classify:
            self.cnt_dict[cl] = 0
            self.correct_dict[cl] = 0

    def __add__(self, other):
        for cl in Acc.classify:
            self.correct_dict[cl] += other.correct_dict[cl]
            self.cnt_dict[cl] += other.cnt_dict[cl]
        return self

    def __radd__(self, other):
        if other == 0:
            return self
        else:
            return self + other

    def __str__(self):
        return_str = ""
        for cl in Acc.classify:
            return_str += cl + f" {self.correct_dict[cl]}/{self.cnt_dict[cl]} "
        return return_str

    def is_correct(self):
        flag = True
        for key1, key2 in zip(self.cnt_dict.keys(), self.correct_dict.keys()):
            assert key1 == key2
            flag = flag and self.cnt_dict[key1] == self.correct_dict[key1]
        return flag