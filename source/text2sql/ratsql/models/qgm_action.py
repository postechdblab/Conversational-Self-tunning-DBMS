from typing import NewType
import json
import ratsql.utils.registry

Symbol = NewType("Symbol", str)
Action = NewType("Action", str)


class QGM_ACTION:
    instance = None

    @classmethod
    def get_instance(cls, state_action_path=None):
        if cls.instance is None:
            cls.instance = QGM_ACTION(state_action_path)
        return cls.instance

    def __init__(self, state_action_path):
        with open(state_action_path) as f:
            self.state_action_dict = json.load(f)

        self.state_action_dict["C"] = []
        self.state_action_dict["T"] = []

        self.symbol_action_id_mapping = dict()
        self.action_id_to_prob_action = dict()
        self.actions = []
        action_id = 0
        for symbol, actions in self.state_action_dict.items():
            self.symbol_action_id_mapping[symbol] = dict()
            for action in actions:
                self.symbol_action_id_mapping[symbol][action] = action_id
                self.action_id_to_prob_action[action_id] = (symbol, action)
                self.actions.append(action)
                action_id += 1
        self.impossible_action_indices = []
        for id in range(action_id):
            if self.action_id_to_prob_action[id][1] in ["BOX_SELECTION_INTERSECT", "BOX_SELECTION_UNION", "BOX_SELECTION_MINUS",
        "SELECTION_COL_EXIST_YES", "SELECTION_COL_EXIST_NO",
        "PREDICATE_COL_EXIST_YES", "PREDICATE_COL_EXIST_NO",
        "SUPER_COL_EXIST_YES", "SUPER_COL_EXIST_NO",
        "ORDER_COL_EXIST_YES", "ORDER_COL_EXIST_NO",
        "GROUPBY_COL_EXIST_YES", "GROUPBY_COL_EXIST_NO",

        "COL_NUM_SELECTION_6", "COL_NUM_SELECTION_7", "COL_NUM_SELECTION_8", "COL_NUM_SELECTION_9", "COL_NUM_SELECTION_10",
        "COL_NUM_SELECTION_11", "COL_NUM_SELECTION_12",
        "COL_SELECTION",
        "OP_SELECTION_IN", "OP_SELECTION_NOT"]:
                self.impossible_action_indices.append(id)

    @classmethod
    def total_action_len(cls):
        return sum(
            [
                len(actions)
                for prob, actions in cls.get_instance().state_action_dict.items()
            ]
        )

    @classmethod
    def total_symbol_len(cls):
        return len(cls.get_instance().state_action_dict)

    @classmethod
    def symbol_action_to_action_id(cls, symbol: str, action: str):
        # if action == "OP_SELECTION_JOININ":
        #     assert False
        return cls.get_instance().symbol_action_id_mapping[symbol][action]

    @classmethod
    def symbol_to_symbol_id(cls, symbol: str):
        for index, (origin_symbol, _) in enumerate(
            cls.get_instance().state_action_dict.items()
        ):
            if symbol == origin_symbol:
                return index
        raise Exception

    @classmethod
    def action_id_to_action(cls, action_id: int):
        return cls.get_instance().action_id_to_prob_action[action_id][1]

    @classmethod
    def possible_actions(cls, symbol: str):
        action_to_id_dict = cls.get_instance().symbol_action_id_mapping[symbol]
        return list(action_to_id_dict.keys())

