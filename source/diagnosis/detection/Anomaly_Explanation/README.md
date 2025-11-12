# Anomaly Detection and Explanation
We develop deep learning model that detects and explain anomaly in multivariate time series data.

Our model is based on [Anomaly Transformer: Time Series Anomaly Detection with Association Discrepancy (ICLR'22)](https://openreview.net/forum?id=LzQQ89U1qm_). We train and evaluate the model on [DBSherlock dataset](https://github.com/hyukkyukang/DBSherlock).

## Anomaly Transformer

Anomaly transformer is a transformer-based model that detects anomaly in multivariate time series data. It is based on the assumption that the normal data is highly correlated, while the abnormal data is not. It uses a transformer encoder to learn the correlation between different time steps, and then uses a discriminator to distinguish the normal and abnormal data based on the learned correlation.

- An inherent distinguishable criterion as **Association Discrepancy** for detection.
- A new **Anomaly-Attention** mechanism to compute the association discrepancy.
- A **minimax strategy** to amplify the normal-abnormal distinguishability of the association discrepancy.

<p align="center">
<img src=".\pics\structure.png" height = "350" alt="" align=center />
</p>

For more details, please refer to the [paper](https://openreview.net/forum?id=LzQQ89U1qm_).

## Environment Setup
Start docker container using docker compose, and login to the container

```bash
docker compose up -d
```
Install python packages
```bash
pip install -r requirements.txt
```

## Testing

```bash
CUDA_VISIBLE_DEVICES=0 python /root/Anomaly_Explanation/src/main.py --num_epochs=10 --batch_size=1024 --mode=test --dataset=DBS --win_size=25 --step_size=25 --data_path=dataset/dbsherlock/converted/tpcc_500w_test.json --find_best=True --add_stats=True
```

## Reference
This respository is based on [Anomaly Transformer](https://github.com/thuml/Anomaly-Transformer).

```
@inproceedings{
xu2022anomaly,
title={Anomaly Transformer: Time Series Anomaly Detection with Association Discrepancy},
author={Jiehui Xu and Haixu Wu and Jianmin Wang and Mingsheng Long},
booktitle={International Conference on Learning Representations},
year={2022},
url={https://openreview.net/forum?id=LzQQ89U1qm_}
}
```