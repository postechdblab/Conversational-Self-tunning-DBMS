# UniTune

This is the source code to the paper "A Unified and Efficient Coordinating Framework  for Autonomous DBMS Tuning". Please refer to the paper for the experimental details.

## Table of Content
* Benchmark Preparation
* Installation
* Experimental Evaluation
* Extendability
 

## Installation
1. Preparations: Python == 3.7

2. Install packages

   ```shell
   pip install -r requirements.txt
   ```

## Benchmark Preparation

### Join-Order-Benchmark (JOB)

Download IMDB Data Set from http://homepages.cwi.nl/~boncz/job/imdb.tgz.

Follow the instructions to load data
 * For MySQL: https://github.com/winkyao/join-order-benchmark.

### TPC-H
Download TPC-H Data Set from https://www.tpc.org/.

Follow the instructions to load data:
 * For MySQL: https://github.com/catarinaribeir0/queries-tpch-dbgen-mysql

## Experimental Evaluation

### Setup

Please modify the user-specified parameters in `config.ini` before the experiments.

* To specify the database connection information, please modify the following parameters:
```shell
[database]
dbtype = mysql
host = 127.0.0.1
port = 3306
user = root
passwd =
dbname = tpch
sock = /mysql/base/mysql.sock
cnf = /MultiTune/default.cnf
# mysql related
mysqld = mysql/mysqlInstall/bin/mysqld
# knob related
knob_config_file =  /MultiTune/knob_configs/mysql_new.json
knob_num = 50
# workload name in ['TPCH', 'JOB']
workload_name = TPCH
# workload execution time constraint in sec
workload_timeout = 600
# workload queries list
workload_qlist_file = /MultiTune/scripts/tpch_queries_list_0.txt
# workload queries directory
workload_qdir = /MultiTune/queries/tpch_queries_mysql_0/
# workload run_scripts directory
scripts_dir = /MultiTune/scripts/
# view generation dir
q_mv_file = /MultiTune/advisor/av_files/trainset/q_mv_list.txt
mv_trainset_dir = /MultiTune/advisor/av_files/trainset

```
* To specify the tuning setting ,please modify the following parameters:
```shell
[tuning]
task_id = tpch_test
components = {'knob': 'OtterTune', 'index':'DBA-Bandit', 'query':'LearnedRewrite'}
tuning_budget = 108000
sub_budget = 1200
context = True
context_type = im
context_pca_components = 5
output_file = optimize_history/tpch_test.res
index_budget = 6500
arm_method = ts
ts_use_window = True
window_size = 7
cost_aware = True
max_runs = 200
block_runs = 2

init_runs = 10
converage_judge = False
test = False

```


### Run
To start a training session, please run:
  ```python
  python main.py
  ```

## Extendability
To add a new agent, a developer needs inherit the corresponding base class and overrides its functions.
Please refer to MultiTune/advisor/adviser_example.py for an example.

