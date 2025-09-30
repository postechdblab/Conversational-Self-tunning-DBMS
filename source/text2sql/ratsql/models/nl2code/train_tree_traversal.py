import operator

import attr
import pyrsistent
import torch

from source.text2sql.ratsql.models.nl2code.tree_traversal import TreeTraversal
from source.text2sql.ratsql.utils.analysis import cal_attention_flow


@attr.s
class ChoiceHistoryEntry:
    rule_left = attr.ib()
    choices = attr.ib()
    probs = attr.ib()
    att_probs = attr.ib()
    memory_pointer_probs = attr.ib(default=None)


class TrainTreeTraversal(TreeTraversal):

    @attr.s(frozen=True)
    class XentChoicePoint:
        logits = attr.ib()

        def compute_loss(self, outer, idx, extra_indices):
            if extra_indices:
                logprobs = torch.nn.functional.log_softmax(self.logits, dim=1)
                valid_logprobs = logprobs[:, [idx] + extra_indices]
                return outer.model.multi_loss_reduction(valid_logprobs)
            else:
                # idx shape: batch (=1)
                idx = outer.model._tensor([idx])
                # loss_piece shape: batch (=1)
                return outer.model.xent_loss(self.logits, idx)

    @attr.s(frozen=True)
    class TokenChoicePoint:
        lstm_output = attr.ib()
        gen_logodds = attr.ib()

        def compute_loss(self, outer, token, extra_tokens):
            return outer.model.gen_token_loss(
                self.lstm_output, self.gen_logodds, token, outer.desc_enc
            )

    def __init__(self, model, desc_enc, debug=False, columns=None, tables=None):
        super().__init__(model, desc_enc)
        self.choice_point = None
        self.loss = pyrsistent.pvector()

        self.debug = debug
        self.history = pyrsistent.pvector()

        if columns:
            self.columns = [" ".join(column[:-1]) for column in columns]
        if tables:
            self.tables = tables

    def clone(self):
        super_clone = super().clone()
        super_clone.choice_point = self.choice_point
        super_clone.loss = self.loss
        super_clone.debug = self.debug
        super_clone.history = self.history
        return super_clone

    def rule_choice(self, node_type, rule_logits, attention_probs):
        self.choice_point = self.XentChoicePoint(rule_logits)
        if self.debug:
            choices = []
            probs = []
            for rule_idx, logprob in sorted(
                self.model.rule_infer(node_type, rule_logits),
                key=operator.itemgetter(1),
                reverse=True,
            ):
                _, rule = self.model.preproc.all_rules[rule_idx]
                choices.append(rule)
                probs.append(logprob.exp().item())
            attention_flow = cal_attention_flow(attention_probs).cpu().numpy().tolist()
            self.history = self.history.append(
                ChoiceHistoryEntry(node_type, choices, probs, attention_flow)
            )

    def token_choice(self, output, gen_logodds):
        self.choice_point = self.TokenChoicePoint(output, gen_logodds)

    def pointer_choice(self, node_type, logits, attention_logits, memory_pointer_probs):
        self.choice_point = self.XentChoicePoint(logits)
        self.attention_choice = self.XentChoicePoint(attention_logits)
        if self.debug:
            memory_pointer_probs = memory_pointer_probs.cpu().numpy().tolist()
            atten_flow = cal_attention_flow(attention_logits).cpu().numpy().tolist()
            assert node_type in ["column", "table"]
            choices = self.columns if node_type == "column" else self.tables
            probs = (
                torch.nn.functional.softmax(logits, dim=-1)
                .squeeze(0)
                .cpu()
                .numpy()
                .tolist()
            )
            # # Sort
            # sorted_items = sorted([(a, b) for a, b in zip(choices, probs)], key=operator.itemgetter(1), reverse=True)
            # choices = [item[0] for item in sorted_items]
            # probs = [item[1] for item in sorted_items]
            # Log
            self.history = self.history.append(
                ChoiceHistoryEntry(
                    node_type, choices, probs, atten_flow, memory_pointer_probs
                )
            )

    def update_using_last_choice(
        self, last_choice, extra_choice_info, attention_offset
    ):
        super().update_using_last_choice(
            last_choice, extra_choice_info, attention_offset
        )
        if last_choice is None:
            return

        if self.debug and isinstance(self.choice_point, self.XentChoicePoint):
            valid_choice_indices = [last_choice] + (
                [] if extra_choice_info is None else extra_choice_info
            )
            self.history[-1].valid_choices = [
                self.model.preproc.all_rules[rule_idx][1]
                for rule_idx in valid_choice_indices
            ]

        self.loss = self.loss.append(
            self.choice_point.compute_loss(self, last_choice, extra_choice_info)
        )

        if attention_offset is not None and self.attention_choice is not None:
            self.loss = self.loss.append(
                self.attention_choice.compute_loss(
                    self, attention_offset, extra_indices=None
                )
            )

        self.choice_point = None
        self.attention_choice = None
