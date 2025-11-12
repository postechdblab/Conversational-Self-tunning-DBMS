import logging
import os
from typing import *

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from torch.utils.data import DataLoader

from data_factory.dataloader import get_dataloader
from model.AnomalyTransformer import AnomalyTransformer
from src.data_factory.data import ANOMALY_CAUSES
from utils.utils import *

from scipy.spatial import distance
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
np.random.seed(2000)
logger = logging.getLogger("Solver")


def calculate_classification_accuracy(cls_probs, classes, labels) -> Tuple[int, int]:
    if type(cls_probs) == np.ndarray and len(cls_probs.shape) == 1:
        predicted = cls_probs
        gold = classes
    else:
        _, predicted = torch.max(cls_probs.data, 2)
        _, gold = torch.max(classes, 2)

    # Filter only anomaly regions
    predicted_for_anomaly_regions = predicted[labels == 1]
    gold_for_anomaly_regions = gold[labels == 1]
    if type(gold_for_anomaly_regions) == torch.Tensor:
        predicted_for_anomaly_regions = predicted_for_anomaly_regions.cpu()
        gold_for_anomaly_regions = gold_for_anomaly_regions.cpu()

    # Count correct
    cls_correct_cnt = (
        (predicted_for_anomaly_regions == gold_for_anomaly_regions).sum().item()
    )
    cls_total_num_cnt = len(predicted_for_anomaly_regions)

    (
        cls_precision,
        cls_recall,
        cls_f_score,
        cls_support,
    ) = precision_recall_fscore_support(
        gold_for_anomaly_regions,
        predicted_for_anomaly_regions,
        average="micro",
    )

    return cls_correct_cnt, cls_total_num_cnt


def my_kl_loss(p, q):
    res = p * (torch.log(p + 0.0001) - torch.log(q + 0.0001))
    return torch.mean(torch.sum(res, dim=-1), dim=1)


def adjust_learning_rate(optimizer, epoch, lr_):
    lr_adjust = {epoch: lr_ * (0.99 ** ((epoch - 1) // 1))}
    if epoch in lr_adjust.keys():
        lr = lr_adjust[epoch]
        for param_group in optimizer.param_groups:
            param_group["lr"] = lr
        logger.info("Updating learning rate to {}\n".format(lr))


class EarlyStopping:
    def __init__(self, patience=7, verbose=False, dataset_name="", delta=0):
        self.patience = patience
        self.verbose = verbose
        self.counter = 0
        self.best_score = None
        self.best_score2 = None
        self.best_score3 = None
        self.best_accuracy = None
        self.early_stop = False
        self.val_loss_min = np.inf
        self.val_loss2_min = np.inf
        self.delta = delta
        self.dataset = dataset_name

    def __call__(self, val_loss, val_loss2, val_loss3, accuracy, model, path):
        score = -val_loss
        score2 = -val_loss2
        score3 = -val_loss3
        if self.best_score is None:
            self.best_score = score
            self.best_score2 = score2
            self.best_score3 = score3
            self.best_accuracy = accuracy
            self.save_checkpoint(val_loss, val_loss2, val_loss3, model, path)
        elif (
            (
                score < self.best_score + self.delta
                or score2 < self.best_score2 + self.delta
            )
            and score3 < self.best_score3 + self.delta
            and accuracy < self.best_accuracy + self.delta
        ):
            self.counter += 1
            logger.info(f"EarlyStopping counter: {self.counter} out of {self.patience}")
            if self.counter >= self.patience:
                self.early_stop = True
        else:
            self.best_score = score
            self.best_score2 = score2
            self.best_score3 = score3
            self.best_accuracy = accuracy
            self.save_checkpoint(val_loss, val_loss2, val_loss3, model, path)
            self.counter = 0

    def save_checkpoint(self, val_loss, val_loss2, val_loss3, model, path):
        if self.verbose:
            logger.info(
                f"Validation loss decreased ({self.val_loss_min:.6f} --> {val_loss:.6f}).  Saving model ..."
            )
        torch.save(model.state_dict(), path)
        self.val_loss_min = val_loss
        self.val_loss2_min = val_loss2
        self.val_loss3_min = val_loss3


class Solver(object):
    DEFAULTS = {}

    def __init__(self, config):
        self.__dict__.update(Solver.DEFAULTS, **config)

        self.train_loader = get_dataloader(
            data_path=self.data_path,
            batch_size=self.batch_size,
            win_size=self.win_size,
            step=self.step_size,
            mode="train",
            dataset=self.dataset,
        )
        self.val_loader = get_dataloader(
            data_path=self.data_path,
            batch_size=self.batch_size,
            win_size=self.win_size,
            step=self.step_size,
            mode="val",
            dataset=self.dataset,
        )
        self.test_loader = get_dataloader(
            data_path=self.data_path,
            batch_size=self.batch_size,
            win_size=self.win_size,
            step=self.step_size,
            mode="test",
            dataset=self.dataset,
        )
        self.thre_loader = get_dataloader(
            data_path=self.data_path,
            batch_size=self.batch_size,
            win_size=self.win_size,
            step=self.step_size,
            mode="thre",
            dataset=self.dataset,
        )
        self.build_model()
        self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        self.criterion = nn.MSELoss()
        self.cross_entropy = nn.CrossEntropyLoss()
        self.softmax = nn.Softmax(dim=2)
        self.temperature = 50
        self.loaded_dataset = self.load_dataset()
    @property
    def model_save_path(self) -> str:
        return os.path.join(self.model_dir_path, f"{self.dataset}_checkpoint.pth")

    def build_model(self):
        self.model = AnomalyTransformer(
            win_size=self.win_size, enc_in=self.input_c, c_out=self.output_c, e_layers=3
        )
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=self.lr)

        if torch.cuda.is_available():
            self.model.cuda()

    def train(self):
        self.model.train()
        logger.info("======================TRAIN MODE======================")

        early_stopping = EarlyStopping(
            patience=20, verbose=True, dataset_name=self.dataset
        )

        for epoch in range(self.num_epochs):
            loss1_list = []

            for i, (input_data, labels, classes, is_overlaps) in enumerate(
                self.train_loader
            ):
                self.optimizer.zero_grad()
                input = input_data.float().to(self.device)

                cls_out, output, series, prior, _ = self.model(input)

                loss1, loss2, loss3 = self.compute_loss(
                    input=input,
                    recon_output=output,
                    classify_output=cls_out,
                    anomaly_labels=labels,
                    anomaly_causes=classes,
                    series=series,
                    prior=prior,
                )

                loss1_list.append(loss1.item())

                # Minimax strategy
                loss1.backward(retain_graph=True)
                if self.add_classifier:
                    loss2.backward(retain_graph=True)
                    loss3.backward()
                else:
                    loss2.backward()
                self.optimizer.step()

            avg_train_loss = np.average(loss1_list)

            # Compute validateion loss and accuracy
            vali_loss1, vali_loss2, vali_loss3, accuracy = self.vali(self.test_loader)
            self.model.train()

            logger.info(
                "Epoch: {0}, Steps: {1} | Train Loss: {2:.7f} Vali Loss: {3:.7f} Vali acc: {4:.7f} ".format(
                    epoch + 1,
                    len(self.train_loader),
                    avg_train_loss,
                    vali_loss1,
                    accuracy,
                )
            )
            early_stopping(
                vali_loss1,
                vali_loss2,
                vali_loss3,
                accuracy,
                self.model,
                self.model_save_path,
            )
            if early_stopping.early_stop:
                logger.info("Early stopping")
                break

            adjust_learning_rate(self.optimizer, epoch + 1, self.lr)

    def vali(self, data_loader):
        self.model.eval()

        loss_1 = []
        loss_2 = []
        loss_3 = []

        cls_num_cnt = 0
        cls_correct_cnt = 0
        for i, (input_data, labels, classes, _) in enumerate(data_loader):
            input = input_data.float().to(self.device)
            cls_output, output, series, prior, _ = self.model(input)

            # Compute series loss and prior loss
            series_loss, prior_loss = self.compute_series_prior_loss(
                series, prior, do_mean=True
            )

            series_loss = series_loss / len(prior)
            prior_loss = prior_loss / len(prior)

            rec_loss = self.criterion(output, input)
            pred_cls_probs = self.softmax(cls_output)
            gold_cls_probs = (
                torch.nn.functional.one_hot(
                    classes.long(),
                    num_classes=len(ANOMALY_CAUSES),
                )
                .float()
                .cuda()
            )
            cls_loss = self.cross_entropy(pred_cls_probs, gold_cls_probs)
            loss_1.append((rec_loss - self.k * series_loss).item())
            loss_2.append((rec_loss + self.k * prior_loss).item())
            loss_3.append(cls_loss.item())

            # Accumulate accuracy
            correct_cnt, total_cnt = calculate_classification_accuracy(
                pred_cls_probs, gold_cls_probs, labels
            )
            cls_correct_cnt += correct_cnt
            cls_num_cnt += total_cnt

        accuracy = cls_correct_cnt / cls_num_cnt

        return np.average(loss_1), np.average(loss_2), np.average(loss_3), accuracy

    def test(self):
        self.model.load_state_dict(torch.load(self.model_save_path))
        self.model.eval()

        logger.info("======================TEST MODE======================")

        # Find stats on train and validation set
        train_energy, train_labels = self.get_attention_energy(self.train_loader)
        val_energy, val_labels = self.get_attention_energy(self.val_loader)
        val_overlapping_flags = []
        for i, (input_data, labels, classes, is_overlaps) in enumerate(
            self.val_loader
        ):
            val_overlapping_flags.append(is_overlaps)
        val_overlapping_flags = np.concatenate(val_overlapping_flags, axis=0).reshape(-1)
        val_overlapping_flags = np.array(val_overlapping_flags)
        # Find the threshold
        # combined_energy = np.concatenate([train_energy, val_energy], axis=0)
        # combined_labels = np.concatenate([train_labels, val_labels], axis=0)

        if self.find_best:
            thresh, lamda, dim = self.find_best_threshold(val_energy, val_labels, val_overlapping_flags)
        else:
            lamda = None
            thresh = np.percentile(val_energy, 100 - self.anormly_ratio)
        logger.info(f"Threshold : {thresh}")
        # Inference on the test set
        criterion = nn.MSELoss(reduction="none")
        test_labels = []
        overlapping_flags = []
        attens_energy = []
        cls_preds = []
        cls_golds = []
        for i, (input_data, labels, classes, is_overlaps) in enumerate(
            self.test_loader
        ):
            input = input_data.float().to(self.device)
            cls_output, output, series, prior, _ = self.model(input)

            loss = torch.mean(criterion(input, output), dim=-1)

            # Compute series loss and prior loss
            series_loss, prior_loss = self.compute_series_prior_loss(series, prior)
            metric = torch.softmax((-series_loss - prior_loss), dim=-1)

            # Compute classification accuracy
            cls_prob = self.softmax(cls_output)
            _, cls_predicted = torch.max(cls_prob.data, 2)
            cls_gold = classes

            cri = metric * loss
            cri = cri.detach().cpu().numpy()
            attens_energy.append(cri)
            test_labels.append(labels)
            cls_preds.append(cls_predicted)
            cls_golds.append(cls_gold)
            overlapping_flags.append(is_overlaps)

        attens_energy = np.concatenate(attens_energy, axis=0).reshape(-1)
        test_labels = np.concatenate(test_labels, axis=0).reshape(-1)
        overlapping_flags = np.concatenate(overlapping_flags, axis=0).reshape(-1)
        test_energy = np.array(attens_energy)
        test_labels = np.array(test_labels)
        overlapping_flags = np.array(overlapping_flags)
        cls_preds = np.array(torch.stack(cls_preds).cpu()).reshape(-1)
        cls_golds = np.array(torch.stack(cls_golds).cpu()).reshape(-1)
        if lamda is not None:
            if lamda==0.0:
                test_energy = test_energy
            else:
                if dim is not None:
                    stats = self.get_distances('test', 'pca', dim)
                else:
                    stats = self.get_distances('test')
                test_energy = test_energy + lamda*stats
        # thresh = np.percentile(test_energy, 100 - anomaly_ratio)
        # Evaluate
        accuracy, precision, recall, f_score = self.get_metrics_for_threshold(
            test_energy,
            test_labels,
            thresh,
            cls_preds=cls_preds,
            cls_golds=cls_golds,
            is_overlapping=overlapping_flags,
        )
        return accuracy, precision, recall, f_score

    def compute_loss(
        self,
        input: torch.Tensor,
        recon_output: torch.Tensor,
        classify_output: torch.Tensor,
        anomaly_labels: torch.Tensor,
        anomaly_causes: torch.Tensor,
        series: List[torch.Tensor],
        prior: List[torch.Tensor],
    ) -> Tuple[float, float, float]:
        # calculate Association discrepancy
        series_loss, prior_loss = self.compute_series_prior_loss(
            series, prior, do_mean=True
        )

        # Average
        series_loss = series_loss / len(prior)
        prior_loss = prior_loss / len(prior)

        rec_loss = self.criterion(recon_output, input)
        cls_probs = self.softmax(classify_output)

        # Change gold anomaly cause id to probs
        anomaly_causes_probs = (
            torch.nn.functional.one_hot(
                anomaly_causes.long(),
                num_classes=len(ANOMALY_CAUSES),
            )
            .float()
            .cuda()
        )

        # Filter only anomaly regions
        cls_probs_for_anomaly_regions = cls_probs[anomaly_labels == 1]
        causes_for_anomaly_regions = anomaly_causes_probs[anomaly_labels == 1]
        classification_loss = self.cross_entropy(
            cls_probs_for_anomaly_regions, causes_for_anomaly_regions
        )

        loss1 = rec_loss - self.k * series_loss
        loss2 = rec_loss + self.k * prior_loss
        if self.add_classifier:
            loss3 = classification_loss
        else:
            loss3 = 0.0

        return loss1, loss2, loss3

    def compute_series_prior_loss(
        self,
        series: List[torch.Tensor],
        prior: List[torch.Tensor],
        do_mean: bool = False,
    ) -> Tuple[float, float]:
        if do_mean:
            series_loss = 0.0
            prior_loss = 0.0
        for u in range(len(prior)):
            if do_mean:
                series_loss += torch.mean(
                    my_kl_loss(
                        series[u],
                        (
                            prior[u]
                            / torch.unsqueeze(
                                torch.sum(prior[u], dim=-1), dim=-1
                            ).repeat(1, 1, 1, self.win_size)
                        ).detach(),
                    )
                ) + torch.mean(
                    my_kl_loss(
                        (
                            prior[u]
                            / torch.unsqueeze(
                                torch.sum(prior[u], dim=-1), dim=-1
                            ).repeat(1, 1, 1, self.win_size)
                        ).detach(),
                        series[u],
                    )
                )
                prior_loss += torch.mean(
                    my_kl_loss(
                        (
                            prior[u]
                            / torch.unsqueeze(
                                torch.sum(prior[u], dim=-1), dim=-1
                            ).repeat(1, 1, 1, self.win_size)
                        ),
                        series[u].detach(),
                    )
                ) + torch.mean(
                    my_kl_loss(
                        series[u].detach(),
                        (
                            prior[u]
                            / torch.unsqueeze(
                                torch.sum(prior[u], dim=-1), dim=-1
                            ).repeat(1, 1, 1, self.win_size)
                        ),
                    )
                )
            else:
                if u == 0:
                    series_loss = (
                        my_kl_loss(
                            series[u],
                            (
                                prior[u]
                                / torch.unsqueeze(
                                    torch.sum(prior[u], dim=-1), dim=-1
                                ).repeat(1, 1, 1, self.win_size)
                            ).detach(),
                        )
                        * self.temperature
                    )

                    prior_loss = (
                        my_kl_loss(
                            (
                                prior[u]
                                / torch.unsqueeze(
                                    torch.sum(prior[u], dim=-1), dim=-1
                                ).repeat(1, 1, 1, self.win_size)
                            ),
                            series[u].detach(),
                        )
                        * self.temperature
                    )
                else:
                    series_loss += (
                        my_kl_loss(
                            series[u],
                            (
                                prior[u]
                                / torch.unsqueeze(
                                    torch.sum(prior[u], dim=-1), dim=-1
                                ).repeat(1, 1, 1, self.win_size)
                            ).detach(),
                        )
                        * self.temperature
                    )
                    prior_loss += (
                        my_kl_loss(
                            (
                                prior[u]
                                / torch.unsqueeze(
                                    torch.sum(prior[u], dim=-1), dim=-1
                                ).repeat(1, 1, 1, self.win_size)
                            ),
                            series[u].detach(),
                        )
                        * self.temperature
                    )
        return series_loss, prior_loss

    def get_metrics_for_threshold(
        self,
        energy,
        labels,
        thresh,
        cls_preds=None,
        cls_golds=None,
        is_overlapping=None,
    ):
        # Filter only non-overlapping regions
        if is_overlapping is not None:
            energy = energy[is_overlapping == 0]
            labels = labels[is_overlapping == 0]
            if cls_preds is not None:
                cls_preds = cls_preds[is_overlapping == 0]
                cls_golds = cls_golds[is_overlapping == 0]

        pred = (energy > thresh).astype(int)
        gt = labels.astype(int)

        # detection adjustment
        pred = self.detect_adjustment(pred, gt)

        pred = np.array(pred)
        gt = np.array(gt)

        # Compute accuracy
        if cls_preds is None or cls_golds is None:
            before_correct_cnt = 0
            before_total_cnt = 0
            after_correct_cnt = 0
            after_total_cnt = 0
        else:
            before_correct_cnt, before_total_cnt = calculate_classification_accuracy(
                cls_preds, cls_golds, labels
            )

            # Modify the gt labels
            cls_preds = self.explanation_adjustment(
                classification_preds=cls_preds, detection_gt=gt
            )

            after_correct_cnt, after_total_cnt = calculate_classification_accuracy(
                cls_preds, cls_golds, labels
            )

        accuracy = accuracy_score(gt, pred)
        precision, recall, f_score, support = precision_recall_fscore_support(
            gt, pred, average="binary"
        )

        logger.info(
            "Accuracy : {:0.4f}, Precision : {:0.4f}, Recall : {:0.4f}, F-score : {:0.4f} ".format(
                accuracy, precision, recall, f_score
            )
        )
        if before_total_cnt:
            logger.info(
                f"Before acc: {before_correct_cnt / before_total_cnt} ({before_correct_cnt}/{before_total_cnt})"
            )
        if after_total_cnt:
            logger.info(
                f"After acc: {after_correct_cnt / after_total_cnt} ({after_correct_cnt}/{after_total_cnt})"
            )

        return accuracy, precision, recall, f_score

    def find_best_threshold(
        self, val_energy, val_labels, overlapping_flags, ar_range=np.arange(1.0, 5.0, 0.1), lamda_range=np.arange(0.01, 0.05, 0.01), dim_range=np.arange(1, 10, 1)
    ) -> float:
        best_f_score = 0
        best_thresh = None
        best_ar = None
        best_lamda = None
        best_dim = None
        option='pca'
        logger.info("Finding best threshold...")
        if self.add_stats:
            for dim in dim_range:
                distances = self.get_distances('val',option,dim)
                for lamda in lamda_range:
                    val_energy_with_distances = val_energy + lamda * distances
                    for anomaly_ratio in ar_range:
                        logger.info(f"Anomaly Ratio: {anomaly_ratio}")
                        thresh = np.percentile(val_energy_with_distances, 100 - anomaly_ratio)
                        accuracy, precision, recall, f_score = self.get_metrics_for_threshold(
                            val_energy_with_distances, val_labels, thresh, is_overlapping=overlapping_flags,
                        )
                        if f_score > best_f_score:
                            best_f_score = f_score
                            best_thresh = thresh
                            best_ar = anomaly_ratio
                            best_lamda = lamda
                            best_dim = dim
            logger.info(f"Best lamda: {best_lamda}\n")
            logger.info(f"Best dim: {best_dim}\n")
        else:
            for anomaly_ratio in ar_range:
                logger.info(f"Anomaly Ratio: {anomaly_ratio}")
                thresh = np.percentile(val_energy, 100 - anomaly_ratio)
                accuracy, precision, recall, f_score = self.get_metrics_for_threshold(
                    val_energy, val_labels, thresh, is_overlapping=overlapping_flags,
                )
                if f_score > best_f_score:
                    best_f_score = f_score
                    best_thresh = thresh
                    best_ar = anomaly_ratio

        logger.info(f"Best F1 Score: {best_f_score}")
        logger.info(f"Best Anomaly Ratio: {best_ar}\n")
        return best_thresh, best_lamda, best_dim

    def get_attention_energy(
        self, dataloader: DataLoader
    ) -> Tuple[np.ndarray, np.ndarray]:
        criterion = nn.MSELoss(reduction="none")

        all_labels = []
        all_attens_energy = []
        for input_data, labels, _, _ in dataloader:
            input = input_data.float().to(self.device)
            _, output, series, prior, _ = self.model(input)
            loss = torch.mean(criterion(input, output), dim=-1)

            # Compute series loss and prior loss
            series_loss, prior_loss = self.compute_series_prior_loss(series, prior)

            metric = torch.softmax((-series_loss - prior_loss), dim=-1)
            cri = metric * loss
            cri = cri.detach().cpu().numpy()
            all_attens_energy.append(cri)
            all_labels.append(labels)

        all_attens_energy = np.concatenate(all_attens_energy, axis=0).reshape(-1)
        all_labels = np.concatenate(all_labels, axis=0).reshape(-1)

        return np.array(all_attens_energy), np.array(all_labels)

    def detect_adjustment(
        self,
        pred: List[int],
        gold: List[int],
    ) -> List[int]:
        # detection adjustment: please see this issue for more information https://github.com/thuml/Anomaly-Transformer/issues/14

        anomaly_state = False
        for i in range(len(gold)):
            if gold[i] == 1 and pred[i] == 1 and not anomaly_state:
                anomaly_state = True
                for j in range(i, 0, -1):
                    if gold[j] == 0:
                        break
                    else:
                        if pred[j] == 0:
                            pred[j] = 1
                for j in range(i, len(gold)):
                    if gold[j] == 0:
                        break
                    else:
                        if pred[j] == 0:
                            pred[j] = 1
            elif gold[i] == 0:
                anomaly_state = False
            if anomaly_state:
                pred[i] = 1

        return pred

    def explanation_adjustment(
        self, classification_preds: torch.Tensor, detection_gt: torch.Tensor
    ) -> torch.Tensor:
        # Modify the gt labels
        visited_indices = []
        for start_idx in range(len(detection_gt)):
            if start_idx in visited_indices:
                continue
            if detection_gt[start_idx] == 1:
                # Find the range
                for end_idx in range(start_idx, len(detection_gt)):
                    if detection_gt[end_idx] == 0:
                        break

                # get cls preds
                cls_pred_sub = classification_preds[start_idx:end_idx]

                # Find the most frequent class
                tmp = {}
                for cls in cls_pred_sub:
                    if cls not in tmp.keys():
                        tmp[cls] = 0
                    tmp[cls] += 1
                # Sort the dict by value
                tmp = sorted(tmp.items(), key=lambda x: x[1], reverse=True)
                most_frequent_cls = tmp[0][0]
                classification_preds[start_idx:end_idx] = most_frequent_cls
                visited_indices += list(range(start_idx, end_idx))
            else:
                continue

        return classification_preds

    def get_distances(self, mode, option='pca', dim=1):
        scaler = StandardScaler()
        train_data = np.array(scaler.fit_transform(self.loaded_dataset['train']))
        train_label = np.array(self.loaded_dataset['train_label'])
        train_data_normal = train_data[np.where(train_label == 0)[0]]
        train_mean = np.mean(train_data_normal, axis=0)
        
        pca = None
        if option == 'regularize':
            regularization_term = 1e-5
            train_covariance = np.cov(train_data_normal, rowvar=False)
            train_cov_matrix_regularized = train_covariance + regularization_term * np.eye(train_data.shape[1])
            train_cov_inv = np.linalg.inv(train_cov_matrix_regularized)
        elif option == 'pca':
            n_components=dim
            pca = PCA(n_components=n_components)
            train_data_normal = pca.fit_transform(train_data_normal).reshape(-1, n_components) # Ensure 2D shape
            train_mean = np.mean(train_data_normal, axis=0).reshape(-1) # Ensure 1D shape
            train_cov_inv = np.linalg.inv(np.cov(train_data_normal, rowvar=False).reshape(-1, n_components))
        else:
            raise ValueError("Option should be either 'regularize' or 'pca'.")

        if mode == 'val':
            data = np.array(scaler.transform(self.loaded_dataset['val']))
        else:
            data = np.array(scaler.transform(self.loaded_dataset['test']))

        # If PCA option is selected, apply the same transformation to the data
        if pca:
            data = pca.transform(data)

        distances = self.distance(data, train_mean, train_cov_inv)
        if mode == 'val':
            length_list = self.loaded_dataset['val_length']
        else:
            length_list = self.loaded_dataset['test_length']
            
        distances = self.split_distances(distances, length_list)
        distances = self.repreprocess_data(distances, self.step_size)
        distances = np.concatenate(distances, axis=0).reshape(-1)
        return distances
    
    
    def load_dataset(self,):
        dataset = {}
        for partition in ["train", "val", "test"]:
            length_list = []
            all_data = []
            label = []
            if partition == "train":
                dataset_loader = self.train_loader.dataset.train_data_list
            elif partition == "val":
                dataset_loader = self.val_loader.dataset.val_data_list
            else:
                dataset_loader = self.test_loader.dataset.test_data_list
            for i in range(len(dataset_loader)):
                data = dataset_loader[i]
                all_data.extend(data.valid_values)
                length_list.append(len(data.valid_values))
                label.extend([1 if id in data.abnormal_regions else 0 for id, value in enumerate(data.valid_values)])
            dataset[partition] = all_data
            dataset[partition + '_length'] = length_list
            dataset[partition + '_label'] = label
        return dataset
    
    def repreprocess_datum(self, datum, kernel_size):
        window_data_list = []
        for i in range(len(datum) // kernel_size):
            window_data_list.append(datum[i * kernel_size : (i + 1) * kernel_size])
        if len(datum) % kernel_size != 0:
            window_data_list.append(datum[-kernel_size:])
        return window_data_list

    def repreprocess_data(
        self, data, kernel_size
    ):
        all_data = []
        for datum in data:
            datum = self.repreprocess_datum(datum, kernel_size)
            all_data.extend(datum)
        return all_data
    
    def split_distances(self, distances, length_list):
        i = 0
        splitted_distances = []
        for length in length_list:
            splitted_distances.append(distances[i:i+length])
            i = i + length
        return splitted_distances
    
    def distance(self, data, mean, cov_inv):
        distances = []
        for datum in data:
            distances.append(distance.mahalanobis(datum, mean, cov_inv))
        return np.array(distances)