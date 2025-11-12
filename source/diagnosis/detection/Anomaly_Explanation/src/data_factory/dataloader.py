from torch.utils.data import DataLoader

from src.data_factory.dataset.dbsherlock import DBSherlockDataset
from src.data_factory.dataset.msl import MSLDataset
from src.data_factory.dataset.psm import PSMDataset
from src.data_factory.dataset.smd import SMDDataset
from src.data_factory.dataset.smap import SMAPDataset


def get_dataloader(
    data_path: str,
    batch_size: int,
    win_size: int = 100,
    step: int = 100,
    mode: str = "train",
    dataset: str = "KDD",
) -> DataLoader:
    if dataset == "SMD":
        dataset = SMDDataset(data_path, win_size, step, mode)
    elif dataset == "MSL":
        dataset = MSLDataset(data_path, win_size, 1, mode)
    elif dataset == "SMAP":
        dataset = SMAPDataset(data_path, win_size, 1, mode)
    elif dataset == "PSM":
        dataset = PSMDataset(data_path, win_size, 1, mode)
    elif dataset == "DBS":
        dataset = DBSherlockDataset(data_path, win_size, step, mode)

    do_shuffle = mode == "train"

    data_loader = DataLoader(
        dataset=dataset, batch_size=batch_size, shuffle=do_shuffle, num_workers=0
    )
    return data_loader
