"""Tools to save/restore model from checkpoints."""

import collections
import argparse
import shutil
import sys
import os
import re
import json
import time

import torch

CHECKPOINT_PATTERN = re.compile(r"^model_checkpoint-(\d+)$")
CHECKPOINT_PREFIX = "model_checkpoint-"


class ArgsDict(dict):
    def __init__(self, **kwargs):
        super(ArgsDict, self).__init__()
        for key, value in kwargs.items():
            self[key] = value
        self.__dict__ = self


def to_int(object):
    try:
        return int(object)
    except:
        return object


def get_model_ckpt_path(model_dir, step=None):
    # Check and get model checkpoint path
    if not model_dir:
        return model_dir
    model_path = ""
    step = to_int(step)
    if step and type(step) == int:
        # If step is specified, we must load from it to prevent side effects.
        model_path = os.path.join(model_dir, f"model_checkpoint-{step:06d}.pt")
        assert os.path.exists(model_path), f"Checkpoint for step:{step} doesn't exist!"
    else:
        # If the user did not request for the best model, try to load the latest step model
        if step != "best":
            onlyfiles = [
                f
                for f in os.listdir(model_dir)
                if os.path.isfile(os.path.join(model_dir, f))
            ]
            model_files = list(
                sorted(
                    [f for f in onlyfiles if CHECKPOINT_PREFIX in f and ".pt" in f],
                    reverse=True,
                )
            )
            if model_files:
                model_path = os.path.join(model_dir, model_files[0])
        # If there is no latest step, try to load the best model
        if not model_path:
            model_path = os.path.join(model_dir, "best_model.pt")

    return model_path


def load_checkpoint(item_dict, model_dir, map_location=None, step=None):
    """item_dict: {"model": model, "opt1": opt1, ...}"""

    def is_ddp(keys):
        return any(["module." in key for key in keys])

    model_path = get_model_ckpt_path(model_dir, step=step)

    # Load model
    if os.path.exists(model_path):
        print(f"Loading model from {model_path}")
        checkpoint = torch.load(model_path, map_location=map_location)

        # Handle diff in param name due to DDP
        running_model_is_ddp = is_ddp(item_dict["model"].state_dict().keys())
        saved_model_is_ddp = is_ddp(checkpoint["model"].keys())
        if running_model_is_ddp != saved_model_is_ddp:
            if saved_model_is_ddp:
                # Remove module wrapper
                checkpoint["model"] = collections.OrderedDict(
                    {
                        key.replace("module.", ""): value
                        for key, value in checkpoint["model"].items()
                    }
                )
            else:
                # Add module wrapper
                checkpoint["model"] = collections.OrderedDict(
                    {
                        "module." + key: value
                        for key, value in checkpoint["model"].items()
                    }
                )
        # Load params
        old_state_dict = item_dict["model"].state_dict()
        for key in old_state_dict.keys():
            if key not in checkpoint["model"]:
                checkpoint["model"][key] = old_state_dict[key]

        for item_name in item_dict:
            # Remove position id from checkpoint
            for key in [
                k for k, v in checkpoint[item_name].items() if "position_ids" in k
            ]:
                del checkpoint[item_name][key]
            item_dict[item_name].load_state_dict(checkpoint[item_name])

        return checkpoint.get("step", 0), checkpoint.get("best_acc", 0.0)
    print(f"Skip loading model from {model_path}")
    return 0, 0.0


def load_and_map_checkpoint(model, model_dir, remap):
    path = os.path.join(model_dir, "model_checkpoint")
    print("Loading parameters %s from %s" % (remap.keys(), model_dir))
    checkpoint = torch.load(path)
    new_state_dict = model.state_dict()
    for name, value in remap.items():
        # TODO: smarter mapping.
        new_state_dict[name] = checkpoint["model"][value]
    model.load_state_dict(new_state_dict)


def save_checkpoint(
    items, step, model_dir, acc, is_best, ignore=[], keep_every_n=10000000, custom=None
):
    if not os.path.exists(model_dir):
        os.makedirs(model_dir)
    path_for_best = os.path.join(model_dir, "best_model.pt")
    path_without_step = os.path.join(model_dir, CHECKPOINT_PREFIX)
    step_padded = format(step, "06d")
    state_dict = items["model"].state_dict()
    if ignore:
        for key in state_dict.keys():
            for item in ignore:
                if key.startswith(item):
                    state_dict.pop(key)
    path_with_step = f"{path_without_step}{step_padded}.pt"

    saved_dic = {}
    for key in items:
        saved_dic[key] = items[key].state_dict()
    torch.save(
        {**saved_dic, "step": step, "acc": acc, "custom": custom}, path_with_step
    )

    if is_best:
        torch.save(
            {**saved_dic, "step": step, "acc": acc, "custom": custom}, path_for_best
        )
    try:
        os.unlink(path_without_step)
    except FileNotFoundError:
        pass
    try:
        os.symlink(os.path.basename(path_with_step), path_without_step)
    except OSError:
        shutil.copy2(path_with_step, path_without_step)

    # Cull old checkpoints.
    if keep_every_n is not None:
        all_checkpoints = []
        for name in os.listdir(model_dir):
            m = CHECKPOINT_PATTERN.match(name)
            if m is None or name == os.path.basename(path_with_step):
                continue
            checkpoint_step = int(m.group(1))
            all_checkpoints.append((checkpoint_step, name))
        all_checkpoints.sort()

        last_step = float("-inf")
        for checkpoint_step, name in all_checkpoints:
            if checkpoint_step - last_step >= keep_every_n:
                last_step = checkpoint_step
                continue
            os.unlink(os.path.join(model_dir, name))


class Saver(object):
    """Class to manage save and restore for the model and optimizer."""

    def __init__(
        self, items, model_dir, keep_every_n=None, is_main_node=True, custom=None
    ):
        assert type(items) == dict
        assert "model" in items
        self._best_acc = 0
        self._items = items
        self._model_dir = model_dir
        self._keep_every_n = keep_every_n
        self._is_main_node = is_main_node
        self._custom = custom

    def is_new_best(self, acc):
        is_better = acc > self._best_acc
        self._best_acc = acc
        return is_better

    def restore(self, map_location=None, step=None, item_keys=["model", "optimizer"]):
        """Restores model and optimizer from given directory.
            Specify what shoud be restored
            step can be either a number or string as 'best'

        Returns:
           Last training step for the model restored.
        """
        items2restore = {k: self._items[k] for k in item_keys}
        last_step, best_acc = load_checkpoint(
            items2restore, self._model_dir, map_location, step
        )
        self._best_acc = best_acc
        return last_step

    def save(self, step, acc=None):
        """Saves model and optimizer to given directory.
        Args:
           model_dir: Model directory to save.
           step: Current training step.
        """
        if self._is_main_node:
            is_best = self.is_new_best(acc) if acc != None else False
            save_checkpoint(
                self._items,
                step,
                self._model_dir,
                acc,
                is_best,
                keep_every_n=self._keep_every_n,
                custom=self._custom,
            )

    def restore_part(self, other_model_dir, remap):
        """Restores part of the model from other directory.

        Useful to initialize part of the model with another pretrained model.

        Args:
            other_model_dir: Model directory to load from.
            remap: dict, remapping current parameters to the other model's.
        """
        load_and_map_checkpoint(self._items["model"], other_model_dir, remap)
