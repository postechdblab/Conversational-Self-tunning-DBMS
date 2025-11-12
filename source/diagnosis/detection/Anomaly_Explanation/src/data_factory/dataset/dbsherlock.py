import logging
import os
from typing import *

import hkkang_utils.data as data_utils
import hkkang_utils.file as file_utils
import hkkang_utils.list as list_utils
import numpy as np
import torch
from sklearn.preprocessing import StandardScaler
import random
from data_factory.data import ANOMALY_CAUSES
from src.data_factory.data import AnomalyData, AnomalyDataset

SKIP_CAUSES = ["Poor Physical Design"]

logger = logging.getLogger("DBSherlockDataset")


@data_utils.dataclass
class TimeSegment:
    start_time: int
    end_time: int
    value: np.ndarray  # dimension: (time, attribute)
    is_anomaly: List[bool]
    is_overlap: List[bool]
    anomaly_cause: List[int]


class DBSherlockDataset(torch.utils.data.Dataset):
    def __init__(
        self,
        data_path: str,
        win_size: int,
        step: int,
        mode="train",
        skip_causes: Optional[List[str]] = SKIP_CAUSES,
    ):
        self.data_path = data_path
        self.mode = mode
        self.step = step
        self.win_size = win_size
        self.data_split_num = (8, 1, 2)
        self.time_segments: List[TimeSegment] = []
        self.skip_causes = skip_causes if skip_causes else []
        self.__post__init__()

    def __post__init__(self) -> None:
        # Load dataset
        dataset: AnomalyDataset = self.load_dataset(self.data_path)

        # Split dataset
        train_data_list, val_data_list, test_data_list = self.split_dataset(dataset, seed = 120)

        self.train_data_list = train_data_list
        self.val_data_list = val_data_list
        self.test_data_list = test_data_list
        
        if self.mode == "train":
            data_list = train_data_list
        elif self.mode == "val":
            data_list = val_data_list
        elif self.mode == "test":
            data_list = test_data_list
        else:
            data_list = test_data_list
        data_for_fitting = train_data_list

        # Create time segments
        logger.info(f"Creating time segments for {self.mode} mode")
        self.time_segments = list_utils.do_flatten_list(
            [self.create_time_segments(d) for d in data_list]
        )
        segments_for_fitting = list_utils.do_flatten_list(
            [self.create_time_segments(d) for d in data_for_fitting]
        )

        # Scale values
        logger.info(f"Scaling values for {self.mode} mode")
        self.scale_values(segments_for_fitting=segments_for_fitting)
        logger.info(
            f"{self.mode} dataset is ready! ({len(self)} time segments from {len(data_list)} anomaly data)\n"
        )

    def __len__(self) -> int:
        return len(self.time_segments)

    def __getitem__(
        self, index: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        # Get data
        value: np.ndarray = self.time_segments[index].value
        label: List[bool] = self.time_segments[index].is_anomaly
        cause: List[int] = self.time_segments[index].anomaly_cause
        is_overlap: List[bool] = self.time_segments[index].is_overlap

        # Return
        return value, np.float32(label), np.float32(cause), np.float32(is_overlap)

    def load_dataset(self, path: str) -> AnomalyDataset:
        assert path.endswith(".json")
        cache_path = path.replace(".json", ".pkl")
        # Load from cache if exists
        if os.path.isfile(cache_path):
            logger.info(f"Loading dataset from {cache_path}")
            return file_utils.read_pickle_file(cache_path)
        # Load from json file
        logger.info(f"Loading dataset from {path}")
        dataset_dic: Dict = file_utils.read_json_file(path)
        dataset = AnomalyDataset.from_dict(data=dataset_dic)
        # Save to cache
        logger.info(f"Saving dataset to {cache_path}")
        file_utils.write_pickle_file(dataset, cache_path)
        return dataset

    def split_dataset(
        self, dataset: AnomalyDataset, seed: Optional[int] = None
    ) -> Tuple[List[AnomalyData], List[AnomalyData], List[AnomalyData]]:
        train_data = []
        val_data = []
        test_data = []
        if seed is not None:
            random.seed(seed)
        else:
            random.seed(0)
        indicies = list(range(11))
        random.shuffle(indicies)
        cut1 = self.data_split_num[0]
        cut2 = cut1 + self.data_split_num[1]
        train_indicies = indicies[:cut1]
        val_indicies = indicies[cut1:cut2]
        for cause in dataset.causes:
            if cause in self.skip_causes:
                continue
            data_of_cause = dataset.get_data_of_cause(cause)
            for id in range(11):
                if id in train_indicies:
                    train_data.append(data_of_cause[id])
                elif id in val_indicies:
                    val_data.append(data_of_cause[id])
                else:
                    test_data.append(data_of_cause[id])

        return train_data, val_data, test_data

    def create_time_segments(self, data: AnomalyData) -> List[TimeSegment]:
        segments: List[TimeSegment] = []
        total_time = len(data.values)
        assert (
            total_time > self.win_size
        ), f"total_time: {total_time}, win_size: {self.win_size}"

        # Create segments from the given anomaly data
        for start_time in range(0, total_time, self.win_size):
            end_time = min(start_time + self.win_size, total_time)

            # Check if the data is enough for the window size.
            # If not, use overlapping data from the previous segment.
            is_overlap = [False] * self.win_size
            if end_time - start_time < self.win_size:
                # Use overlapping data
                overlap_size = self.win_size - (end_time - start_time)
                is_overlap[:overlap_size] = [True] * overlap_size
                start_time = end_time - self.win_size

            # Create a segment
            value = data.values[start_time:end_time]
            is_anomaly = [
                idx in data.valid_abnormal_regions
                for idx in range(start_time, end_time)
            ]
            cause = ANOMALY_CAUSES.index(data.cause)
            anomaly_cause = [
                cause if is_anomaly[idx] else 0 for idx in range(self.win_size)
            ]
            segments.append(
                TimeSegment(
                    start_time=start_time,
                    end_time=end_time,
                    value=np.array(value)[
                        :, 2:
                    ],  # We ignore first two attributes (following DBSherlock)
                    is_anomaly=is_anomaly,
                    is_overlap=is_overlap,
                    anomaly_cause=anomaly_cause,
                )
            )

        return segments

    def scale_values(
        self, segments_for_fitting: List[TimeSegment]
    ) -> Union[List[float], None]:
        scaler = StandardScaler()

        # Check attribute size of all time segments are the same
        assert len(set([s.value.shape[1] for s in segments_for_fitting])) == 1

        # Calculate means for each attribute
        values = np.vstack([seg.value for seg in segments_for_fitting])

        scaler.fit(values)

        # Scale all values
        for time_segment in self.time_segments:
            time_segment.value = scaler.transform(time_segment.value)
