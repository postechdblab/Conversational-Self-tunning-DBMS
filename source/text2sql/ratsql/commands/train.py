import argparse
import collections
import datetime
import random
import json
import copy
import os

import _jsonnet
import attr
import torch
import tqdm

# These imports are needed for registry.lookup
# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import ast_util

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import datasets

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import grammars

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import models

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import optimizers

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql import beam_search

from source.text2sql.ratsql.utils import registry
from source.text2sql.ratsql.utils import random_state
from source.text2sql.ratsql.utils import saver as saver_mod

# noinspection PyUnresolvedReferences
from source.text2sql.ratsql.utils import vocab

from source.text2sql.ratsql.models.spider import spider_beam_search
from torch.utils.tensorboard import SummaryWriter

from source.text2sql.ratsql.datasets.language_model.dataset import (
    PLMDataset,
    data_collate_fn,
)

LONG_DBS = ["baseball_1"]


@attr.s
class DDPConfig:
    local_rank = attr.ib(default=-1)
    world_size = attr.ib(default=1)
    is_ddp = attr.ib(default=False)
    is_main_node = attr.ib(default=True)

    def sync_nodes(self):
        if self.is_ddp:
            torch.distributed.barrier()


@attr.s
class TrainConfig:
    eval_every_n = attr.ib(default=100)
    report_every_n = attr.ib(default=100)
    save_every_n = attr.ib(default=100)
    keep_every_n = attr.ib(default=1000)

    batch_size = attr.ib(default=32)
    eval_batch_size = attr.ib(default=32)
    max_steps = attr.ib(default=100000)
    num_eval_items = attr.ib(default=None)
    eval_on_train = attr.ib(default=True)
    eval_on_val = attr.ib(default=True)
    eval_on_train_by_acc = attr.ib(default=True)
    eval_on_val_by_acc = attr.ib(default=True)

    # Seed for RNG used in shuffling the training data.
    data_seed = attr.ib(default=None)
    # Seed for RNG used in initializing the model.
    init_seed = attr.ib(default=None)
    # Seed for RNG used in computing the model's training loss.
    # Only relevant with internal randomness in the model, e.g. with dropout.
    model_seed = attr.ib(default=None)

    num_batch_accumulated = attr.ib(default=1)
    clip_grad = attr.ib(default=None)


class Logger:
    def __init__(self, log_path, reopen_to_flush=False, local_rank=-1):
        self.skip_logging = local_rank not in [-1, 0]
        self.log_dir = "/".join(log_path.split("/")[:-1])
        self.reopen_to_flush = reopen_to_flush
        if not self.skip_logging:
            self.summary_writer = SummaryWriter(self.log_dir)
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            self.log_file = open(log_path, "a+")

    def log(self, msg):
        if self.skip_logging:
            return None
        formatted = (
            f"[{datetime.datetime.now().replace(microsecond=0).isoformat()}] {msg}"
        )
        print(formatted)
        if self.log_file:
            self.log_file.write(formatted + "\n")
            if self.reopen_to_flush:
                log_path = self.log_file.name
                self.log_file.close()
                self.log_file = open(log_path, "a+")
            else:
                self.log_file.flush()

    def tensorboard_log(self, tag, value, step):
        if self.skip_logging:
            return None
        self.summary_writer.add_scalar(tag, value, step)

    def log_evaluation_result(self, dic, step):
        if self.skip_logging:
            return None
        file_name = os.path.join(self.log_dir, f"eval_result_{step}.json")
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(json.dumps(dic, indent=4, ensure_ascii=False))


class Trainer:
    def __init__(self, logger, config, model_dir=None):
        self.logger = logger
        self.logger.PLM_save_path = os.path.join(self.logger.log_dir, "PLM.pt")
        self.train_config = registry.instantiate(TrainConfig, config["train"])
        self.data_random = random_state.RandomContext(self.train_config.data_seed)
        self.model_random = random_state.RandomContext(self.train_config.model_seed)
        self.init_random = random_state.RandomContext(self.train_config.init_seed)
        self.ddp_config = DDPConfig(**config["ddp_config"])

        if torch.cuda.is_available():
            device_num = self.ddp_config.local_rank if self.ddp_config.is_ddp else 0
            self.device = torch.device("cuda", device_num)
        else:
            self.device = torch.device("cpu")

        with self.init_random:
            # 0. Construct preprocessors
            self.model_preproc = registry.instantiate(
                registry.lookup("model", config["model"]).Preproc,
                config["model"],
                unused_keys=("name",),
            )
            self.model_preproc.load(saver_mod.get_model_ckpt_path(model_dir))

            # 1. Construct model
            self.model = registry.construct(
                "model",
                config["model"],
                unused_keys=("encoder_preproc", "decoder_preproc"),
                preproc=self.model_preproc,
                device=self.device,
            )
            self.model.to(self.device)
            self.module = self.model
            if self.ddp_config.is_ddp:
                self.model = torch.nn.parallel.DistributedDataParallel(
                    self.model,
                    device_ids=[self.ddp_config.local_rank],
                    output_device=[self.ddp_config.local_rank],
                    find_unused_parameters=True,
                )

        # Evaluation data
        self.logger.log("Preloading training data for evaluation...")
        self.train_orig_data = registry.construct("dataset", config["data"]["train"])
        self.logger.log("Preloading validation data for evaluation...")
        self.val_orig_data = registry.construct("dataset", config["data"]["val"])

        # Filter larg input training data
        self.train_data = self.model_preproc.dataset("train")
        self.val_data = self.model_preproc.dataset("val")
        print(
            f"Before filter len of training data: {len(self.train_data.components[0])}"
        )
        t1, t2 = [], []
        for d1, d2 in zip(*self.train_data.components):
            if d1["db_id"] not in ["baseball_1"]:
                t1.append(d1)
                t2.append(d2)
        self.train_data.components = [t1, t2]
        print(
            f"After filter len of training data: {len(self.train_data.components[0])}"
        )

        # Filter some data (Assumption: the order is not changed from the time of preprocessing)
        self.train_orig_data.examples = self._filter_examples(
            self.train_orig_data.examples, self.train_data.components[0]
        )
        self.val_orig_data.examples = self._filter_examples(
            self.val_orig_data.examples, self.val_data.components[0]
        )

    def _filter_examples(self, examples, preprocessed_data):
        if len(examples) > len(preprocessed_data):
            selected_examples = []
            for example in examples:
                if "utterance" in example.orig.keys():
                    if (
                        example.orig["utterance"]
                        == preprocessed_data[len(selected_examples)]["raw_question"]
                    ):
                        selected_examples.append(example)
                else:
                    if (
                        example.orig["query"]
                        == preprocessed_data[len(selected_examples)]["sql"]
                    ):
                        selected_examples.append(example)
                    if len(selected_examples) == len(preprocessed_data):
                        break
            examples = selected_examples
        return examples

    def sample_data(self, examples, data_components):
        indices = list(range(len(examples)))
        if len(indices) > 200:
            selected_indices = random.sample(indices, 200)
            examples = [examples[i] for i in selected_indices]
        else:
            selected_indices = indices
        filtered_data_components = [[], []]
        for i in selected_indices:
            filtered_data_components[0].append(data_components[0][i])
            filtered_data_components[1].append(data_components[1][i])
        return examples, filtered_data_components

    def train_LM(self, config, modeldir):
        def to_tensor(object, device, is_int=True):
            dtype = torch.long if is_int else torch.float
            return torch.tensor(object, dtype=dtype, device=device)

        # Model
        feature_extractor = torch.nn.Sequential(
            torch.nn.Linear(768, 768), torch.nn.ReLU(), torch.nn.Linear(768, 2)
        ).to(self.device)
        # optimizer
        params = []
        for key, param in self.model.encoder.bert_model.named_parameters():
            params.append(param)
        for key, layer in feature_extractor._modules.items():
            for _, param in layer._parameters.items():
                params.append(param)

        optimizer = torch.optim.Adam(params, lr=config["plm"]["lr"])

        # Get Dataloader
        with self.data_random:
            train_data = PLMDataset(
                config["plm"]["data_path"], self.model.preproc.enc_preproc.tokenizer
            )
            train_data_loader = self._yield_batches_from_epochs(
                torch.utils.data.DataLoader(
                    train_data,
                    batch_size=config["plm"]["batch_size"],
                    drop_last=True,
                    collate_fn=data_collate_fn,
                )
            )
            # Train
            last_step = 0
            for batch in train_data_loader:
                # Quit if too long
                if last_step >= config["plm"]["max_train_steps"]:
                    break
                avg_loss = 0.0
                for _i in range(config["plm"]["num_batch_accumulated"]):
                    if _i > 0:
                        batch = next(train_data_loader)
                    input_list, att_masks_list, tok_type_list, golds = batch
                    input_tensor = to_tensor(input_list, self.device)
                    att_masks_tensor = to_tensor(att_masks_list, self.device)
                    golds = to_tensor(golds, self.device)
                    enc_features = self.model.encoder.bert_model(
                        input_tensor, attention_mask=att_masks_tensor
                    ).last_hidden_state[:, 0, :]
                    logits = feature_extractor(enc_features)
                    probs = torch.nn.functional.log_softmax(logits, dim=1)
                    # Compute loss
                    loss = torch.nn.functional.cross_entropy(probs, golds)
                    norm_loss = loss / config["plm"]["num_batch_accumulated"]
                    norm_loss.backward()
                    avg_loss += norm_loss.item()
                print(f"Step:{last_step}\tLoss:{avg_loss}")
                # Update
                optimizer.step()
                optimizer.zero_grad()
                last_step += 1

        # Save model
        torch.save(
            self.model.encoder.bert_model.state_dict(), self.logger.PLM_save_path
        )
        print(f"Pretrained Language Model saved at {self.logger.PLM_save_path}")

    def train(self, config, modeldir):
        # LOAD Pretrained Language Model if exists
        if os.path.isfile(self.logger.PLM_save_path):
            print("Loading Pretrained Language Model")
            self.model.encoder.bert_model.load_state_dict(
                torch.load(self.logger.PLM_save_path)
            )

        # slight difference here vs. unrefactored train: The init_random starts over here.
        # Could be fixed if it was important by saving random state at end of init
        with self.init_random:
            # We may be able to move optimizer and lr_scheduler to __init__ instead. Empirically it works fine. I think that's because saver.restore
            # resets the state by calling optimizer.load_state_dict.
            # But, if there is no saved file yet, I think this is not true, so might need to reset the optimizer manually?
            # For now, just creating it from scratch each time is safer and appears to be the same speed, but also means you have to pass in the config to train which is kind of ugly.

            # TODO: not nice
            if config["optimizer"].get("name", None) == "bertAdamw":
                bert_params = []
                non_bert_params = []
                for name, _param in self.model.named_parameters():
                    if "bert" in name:
                        bert_params.append(_param)
                    else:
                        non_bert_params.append(_param)
                assert len(bert_params) > 0
                optimizer = registry.construct(
                    "optimizer",
                    config["optimizer"],
                    non_bert_params=non_bert_params,
                    bert_params=bert_params,
                )
            else:
                optimizer = registry.construct(
                    "optimizer", config["optimizer"], params=self.model.parameters()
                )

        # 2. Restore model parameters
        if hasattr(self.model_preproc.dec_preproc, "vocab"):
            preproc_save_dict = {
                "vocab": self.model_preproc.dec_preproc.vocab,
                "sum_type_constructors": self.model_preproc.dec_preproc.sum_type_constructors,
                "field_presence_infos": self.model_preproc.dec_preproc.field_presence_infos,
                "seq_lengths": self.model_preproc.dec_preproc.seq_lengths,
                "primitive_types": self.model_preproc.dec_preproc.primitive_types,
                "all_rules": self.model_preproc.dec_preproc.all_rules,
                "rules_mask": self.model_preproc.dec_preproc.rules_mask,
            }
        else:
            preproc_save_dict = None
        saver = saver_mod.Saver(
            {"model": self.model, "optimizer": optimizer},
            modeldir,
            keep_every_n=self.train_config.keep_every_n,
            is_main_node=self.ddp_config.is_main_node,
            custom=preproc_save_dict,
        )
        last_step = saver.restore(map_location=self.device)
        torch.cuda.empty_cache()

        # Create learning rate scheduler
        with self.init_random:
            lr_scheduler = registry.construct(
                "lr_scheduler",
                config.get("lr_scheduler", {"name": "noop"}),
                param_groups=optimizer.param_groups,
            )
            lr_scheduler.assert_correct_param_order()

        if "pretrain" in config and last_step == 0:
            raise RuntimeError("hkkang: Has not considered this part")
            pretrain_config = config["pretrain"]
            _path = pretrain_config["pretrained_path"]
            _step = pretrain_config["checkpoint_step"]
            pretrain_step = saver.restore(
                _path, step=_step, map_location=self.device, item_keys=["model"]
            )
            saver.save(pretrain_step)  # for evaluating pretrained models
            last_step = pretrain_step

        # 3. Get training data somewhere
        with self.data_random:
            if self.ddp_config.is_ddp:
                self.train_sampler = torch.utils.data.DistributedSampler(
                    self.train_data,
                    num_replicas=self.ddp_config.world_size,
                    rank=self.ddp_config.local_rank,
                    shuffle=True,
                    seed=self.train_config.data_seed,
                    drop_last=True,
                )
            else:
                self.train_sampler = None
            train_data_loader = self._yield_batches_from_epochs(
                torch.utils.data.DataLoader(
                    self.train_data,
                    batch_size=self.train_config.batch_size,
                    shuffle=not self.ddp_config.is_ddp,
                    drop_last=True,
                    collate_fn=lambda x: x,
                    sampler=self.train_sampler,
                )
            )

        # 4. Start training loop
        with self.data_random:
            loss_list = []
            USE_FP16 = False
            for batch in train_data_loader:
                # Quit if too long
                if last_step >= self.train_config.max_steps:
                    break

                # Evaluate with accuracy
                model_type = "cosql" if "cosql" in modeldir else "spider"
                if last_step % self.train_config.eval_every_n == 0:
                    if self.ddp_config.is_main_node:
                        # With training data
                        if (
                            self.train_config.eval_on_train_by_acc
                            and last_step % (self.train_config.eval_every_n * 5) == 0
                        ):
                            self.logger.log("Evaluating with training dataset...")
                            filtered_examples, filtered_data_components = (
                                self.sample_data(
                                    self.train_orig_data.examples,
                                    self.train_data.components,
                                )
                            )

                            train_metrics = self.train_orig_data.Metrics(
                                self.train_orig_data,
                                config["data"]["train"]["tables_paths"][0],
                            )
                            self._eval_model_by_acc(
                                saver,
                                self.logger,
                                self.model,
                                self.module,
                                last_step,
                                train_metrics,
                                filtered_examples,
                                filtered_data_components,
                                "train",
                                model_type,
                            )
                        # With validation data
                        if self.train_config.eval_on_val_by_acc:
                            self.logger.log("Evaluating with validation dataset...")
                            val_metrics = self.train_orig_data.Metrics(
                                self.val_orig_data,
                                config["data"]["train"]["tables_paths"][0],
                            )
                            self._eval_model_by_acc(
                                saver,
                                self.logger,
                                self.model,
                                self.module,
                                last_step,
                                val_metrics,
                                self.val_orig_data.examples,
                                self.val_data.components,
                                "val",
                                model_type,
                            )
                    # For lag tolerance
                    self.ddp_config.sync_nodes()

                # Compute and apply gradient
                if USE_FP16:
                    scaler = torch.cuda.amp.GradScaler()
                with self.model_random:
                    for _i in range(self.train_config.num_batch_accumulated):
                        if _i > 0:
                            batch = next(train_data_loader)
                        if USE_FP16:
                            with torch.cuda.amp.autocast():
                                loss = self.model.forward(batch)
                        else:
                            loss = self.model.forward(batch)
                        norm_loss = loss / self.train_config.num_batch_accumulated
                        if USE_FP16:
                            scaler.scale(norm_loss).backward()
                        else:
                            norm_loss.backward()  # Where DDP communication happenss

                        if self.ddp_config.is_main_node:
                            loss_list.append(
                                norm_loss.item() / self.ddp_config.world_size
                            )  # Division for consistent scale in log (w/ & w/o DDP)

                    if (
                        self.train_config.clip_grad
                        and not config["optimizer"]["freeze_bert"]
                    ):
                        torch.nn.utils.clip_grad_norm_(
                            optimizer.bert_param_group["params"],
                            self.train_config.clip_grad,
                        )

                    # Log learning rate
                    self.logger.tensorboard_log(
                        "lr", lr_scheduler.param_groups[0]["lr"], last_step
                    )

                    if USE_FP16:
                        scaler.step(optimizer)
                        scaler.update()
                    else:
                        optimizer.step()
                    lr_scheduler.update_lr(last_step)
                    optimizer.zero_grad()

                # Report metrics
                if (
                    self.ddp_config.is_main_node
                    and last_step % self.train_config.report_every_n == 0
                ):
                    loss = sum(loss_list) / len(loss_list)
                    self.logger.log(f"Step {last_step}: loss={loss:.4f}")
                    self.logger.tensorboard_log(f"train_loss", loss, last_step)
                    loss_list.clear()

                last_step += 1

                # Run saver
                if last_step % self.train_config.save_every_n == 0:
                    saver.save(last_step)
                    self.ddp_config.sync_nodes()

            # Save final model
            saver.save(last_step)

    def _yield_batches_from_epochs(self, loader):
        self.epoch = 0
        while True:
            if self.ddp_config.is_ddp:
                self.train_sampler.set_epoch(self.epoch)
            for batch in loader:
                yield batch
            self.epoch += 1

    @staticmethod
    def _eval_model_by_acc(
        saver,
        logger,
        model,
        module,
        last_step,
        metrics,
        orig_data,
        eval_data,
        eval_section,
        model_type,
        use_heuristic=True,
    ):
        def nl2code_inferer(module, orig_datum, preproc_item):
            beams = spider_beam_search.beam_search_with_heuristics(
                module,
                orig_datum,
                preproc_item,
                beam_size=1,
                max_steps=250,
                from_cond=False,
            )
            results = []
            for beam in beams:
                _, inferred_code = beam.inference_state.finalize()
                results.append(inferred_code)
            return results

        def nl2intent_inferer(model, preproc_item):
            enc_features = model.encoder([preproc_item[0]])
            logits = model.decoder.decoder_layers(enc_features)
            pred_ids = logits.argmax(dim=1)
            pred_labels = [model.decoder.output_classes[id] for id in pred_ids]
            return pred_labels

        model.eval()
        accs = []
        with torch.no_grad():
            assert len(orig_data) == len(eval_data[0])
            for idx, (orig_datum, enc_preproc, dec_preproc) in tqdm.tqdm(
                enumerate(zip(orig_data, eval_data[0], eval_data[1])),
                total=len(orig_data),
            ):
                preproc_item = (enc_preproc, dec_preproc)
                if model_type == "spider":
                    pred_results = nl2code_inferer(module, orig_datum, preproc_item)
                else:
                    pred_results = nl2intent_inferer(model, preproc_item)
                for pred_result in pred_results:
                    metrics.add(orig_datum, pred_result)

                # For smoke test
                if not last_step and idx < 10:
                    break
            eval_result = metrics.finalize()

            # Print evaluation result
            logger.log(f"Step:{last_step} {eval_section}")
            # Log tensorboard
            if type(eval_result["total_scores"]) == float:
                acc = eval_result["total_scores"]
            else:
                acc = eval_result["total_scores"]["all"]["exact"]
            logger.tensorboard_log(f"{eval_section}_acc", acc, last_step)

            # Save evaluation metrics
            logger.log_evaluation_result(eval_result, last_step)

            # IF is beyond the best accuracy, then save
            if saver.is_new_best(acc):
                saver.save(last_step, acc)

        model.train()


def count_parameters(model):
    params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return params / 1e6


def load_saved_config(logdir):
    if not os.path.exists(logdir):
        return None
    # Load saved config
    onlyfiles = [
        f for f in os.listdir(logdir) if os.path.isfile(os.path.join(logdir, f))
    ]
    config_files = [f for f in onlyfiles if "config-" in f and ".json" in f]
    assert len(config_files) in [0, 1], "More than one config files..."
    if config_files:
        config_file = config_files[0]
        with open(os.path.join(logdir, config_file)) as f:
            old_config = json.load(f)
        return old_config
    return None


def save_config(config, logdir):
    file_name = os.path.join(
        logdir, f'config-{datetime.datetime.now().strftime("%Y%m%dT%H%M%S%Z")}.json'
    )
    with open(file_name, "w") as f:
        json.dump(config, f, sort_keys=True, indent=4)


def config_is_same(c1, c2):
    c1_tmp = copy.deepcopy(c1)
    c2_tmp = copy.deepcopy(c2)
    # Don't compare DDP configuration
    for dic in [c1_tmp, c2_tmp]:
        if "ddp_config" in dic:
            del dic["ddp_config"]
    return c1_tmp == c2_tmp


def main(args, mode="TEXT2SQL"):
    if args.config_args:
        config = json.loads(
            _jsonnet.evaluate_file(args.config, tla_codes={"args": args.config_args})
        )
    else:
        config = json.loads(_jsonnet.evaluate_file(args.config))
    # DDP variables
    config["ddp_config"] = {
        "local_rank": args.local_rank,
        "world_size": args.world_size,
        "is_ddp": args.local_rank != -1 and args.world_size > 1,
        "is_main_node": args.local_rank in [-1, 0],
    }

    if "model_name" in config:
        args.logdir = os.path.join(args.logdir, config["model_name"])

    # Initialize the logger
    reopen_to_flush = config.get("log", {}).get("reopen_to_flush")
    logger = Logger(
        os.path.join(args.logdir, "log.txt"),
        reopen_to_flush,
        local_rank=config["ddp_config"]["local_rank"],
    )

    # Save the config info
    saved_config = load_saved_config(args.logdir)
    if saved_config:
        assert config_is_same(
            config, saved_config
        ), "Current config is inconsistent with the saved one!"
    elif config["ddp_config"]["is_main_node"]:
        save_config(config, args.logdir)
        logger.log(f"Logging to {args.logdir}")

    # Construct trainer
    trainer = Trainer(logger, config, model_dir=args.logdir)
    logger.log(f"Model parameter size:{count_parameters(trainer.module):0.2f}M")
    logger.log(f"Encoder size:{count_parameters(trainer.module.encoder):0.2f}M")
    if getattr(trainer.module.encoder, "bert_model", None):
        logger.log(
            f"\tBert Encoder size:{count_parameters(trainer.module.encoder.bert_model):0.2f}M"
        )
    logger.log(f"Decoder size:{count_parameters(trainer.module.decoder):0.2f}M")

    # Do training
    if mode == "TEXT2SQL":
        trainer.train(config, modeldir=args.logdir)
    elif mode == "PLM":
        trainer.train_LM(config, modeldir=args.logdir)
