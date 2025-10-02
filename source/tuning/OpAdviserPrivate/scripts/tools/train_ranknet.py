import os
import sys
import json
import pandas as pd
from plot import parse_data_onefile
from autotune.utils.constants import MAXINT, SUCCESS
from autotune.utils.history_container import HistoryContainer
from autotune.tuner import DBTuner
from autotune.knobs import initialize_knobs, get_default_knobs
from autotune.utils.config_space import ConfigurationSpace, UniformIntegerHyperparameter, CategoricalHyperparameter, UniformFloatHyperparameter
from autotune.selector.selector import KnobSelector
from autotune.utils.logging_utils import setup_logger, get_logger
from autotune.transfer.tlbo.rgpe import RGPE
from autotune.utils.util_funcs import check_random_state

import pdb
import pandas as pd

setup_logger('GEN_RANK')
use_rgpe = True
test_workload = 'all'

def setup_configuration_space(knob_config_file, knob_num):
    knobs = initialize_knobs(knob_config_file, knob_num)
    knobs_list = []
    config_space = ConfigurationSpace()

    for name in knobs.keys():
        value = knobs[name]
        knob_type = value['type']
        if knob_type == 'enum':
            knob = CategoricalHyperparameter(name, [str(i) for i in value["enum_values"]],
                                             default_value=str(value['default']))
        elif knob_type == 'integer':
            min_val, max_val = value['min'], value['max']
            if  max_val > sys.maxsize:
                knob = UniformIntegerHyperparameter(name, int(min_val / 1000), int(max_val / 1000),
                                                    default_value=int(value['default'] / 1000))
            else:
                knob = UniformIntegerHyperparameter(name, min_val, max_val, default_value=value['default'])
        elif knob_type == 'float':
            min_val, max_val = value['min'], value['max']
            knob = UniformFloatHyperparameter(name, min_val, max_val, default_value=value['default'])
        else:
            raise ValueError('Invalid knob type!')

        knobs_list.append(knob)

    config_space.add_hyperparameters(knobs_list)

    return config_space

def load_history(fileL, config_space):

    data_mutipleL = list()
    for fn in fileL:
        try:
            with open(fn) as fp:
                all_data = json.load(fp)
        except Exception as e:
            print('Encountered exception %s while reading runhistory from %s. '
                  'Not adding any runs!', e, fn, )
            return

        info = all_data["info"]
        data = all_data["data"]
        data_mutipleL = data_mutipleL + data


    file_out = 'history_{}_{}.json'.format(workload, knob_num)
    with open(file_out, "w") as fp:
        json.dump({"info": info, "data": data_mutipleL}, fp, indent=2)

    task_id = workload
    history_container = HistoryContainer(task_id, config_space=config_space)
    history_container.load_history_from_json(file_out)

    return history_container

def get_knob_feature(file, knob_config_file):
    try:
        with open(file) as fp:
            all_data = json.load(fp)
    except Exception as e:
        print('Encountered exception %s while reading runhistory from %s. '
              'Not adding any runs!', e, file, )
        return
    data = all_data["data"]
    knob_tuned = list(data[0]['configuration'].keys())
    knob_template = initialize_knobs(knob_config_file, -1 )
    integer, cateratory = 0, 0
    for knob in knob_tuned:
        if not knob in knob_template.keys():
            print(knob)
            continue
        if knob_template[knob]['type'] == 'integer':
            cateratory = cateratory + 1
        else:
            integer = integer + 1

    return  [integer/(integer+cateratory), cateratory/(integer+cateratory)]

if __name__ == '__main__':
    history_path = '/data2/ruike/DBTune/scripts/DBTune_history/repo3'
    knob_config_file = '../experiment/gen_knobs/mysql_all_197_32G.json'
    workloadL = [ 'sysbench', 'twitter', 'job', 'tpch']
    #workloadL.remove(test_workload)
    task = [ 'smac', 'mbo', 'ddpg', 'ga']
    spaceL = [197, 100, 50, 25, 12, 6]

    config_space = setup_configuration_space(knob_config_file, -1)

    if use_rgpe:
    ###setup source workload
        sourceL = list()
        for workload in workloadL:
            fileL = list()
            for method in task:
                for knob_num in spaceL:
                    file = 'history_{}_{}_{}.json'.format(workload, method, knob_num)
                    file = os.path.join(history_path, file)
                    fileL.append(file)
            history_container = load_history(fileL, config_space)
            sourceL.append(history_container)

        rng = check_random_state(100)
        seed = 42
        rgpe = RGPE(config_space, sourceL, 42, num_src_hpo_trial=-1, only_source=False)

    import matplotlib.pyplot as plt
    df = pd.DataFrame(columns=task + workloadL + ['target', 'id', 'rank'] + ['knob_num', 'integer', 'enum' ,'iteration'])
    id = 0
    for workload in workloadL:
        for knob_num in spaceL:
            y_incumbs = list()
            file = 'history_{}_{}_{}.json'.format(workload, task[0], knob_num)
            file = os.path.join(history_path, file)
            knob_feature = get_knob_feature(file, knob_config_file)
            for method in task:
                file = 'history_{}_{}_{}.json'.format(workload, method, knob_num)
                file = os.path.join(history_path, file)
                task_id = '{}_{}_{}'.format(workload, knob_num, method)
                print('load history from {}'.format(file))
                history_container = HistoryContainer(task_id, config_space=config_space)
                history_container.load_history_from_json(file)
                ys = history_container.get_transformed_perfs()

                y_incumb = list()
                best_y = 1e9
                for y_ in ys:
                    if best_y > y_:
                        best_y = y_
                    y_incumb.append(best_y)
                y_incumbs.append(y_incumb)
                plt.plot(y_incumb, label=method)

            plt.legend()
            plt.savefig("plot/rank_{}_{}.png".format(workload, knob_num))
            plt.close()
            n_range = min([len(ys) for ys in y_incumbs])
            if use_rgpe:
                rgpe.iteration_id = 0
            for i in range(n_range):
                # get rank
                perfs = [y[i] for y in y_incumbs ]
                perfs = pd.Series(perfs)
                rank = perfs.rank().values   # the smaller, the better
                if use_rgpe:
                #get workload feature
                    history_container = HistoryContainer(task_id, config_space=config_space)
                    history_container.load_history_from_json(file, load_num=i+1)
                    #rgpe.train(history_container, weight_dilution=False)
                    rank_loss = rgpe.get_ranking_loss(history_container)
                for j in range(len(task)):
                    if not use_rgpe:
                    #onehot
                        temp = [0] * (len(task) + len(workloadL))
                        temp[j] = 1
                        temp[len(task) + workloadL.index(workload)] = 1
                    else:
                    # #similarity
                        temp = [0] * len(task)
                        temp[j] = 1
                        #temp = temp + rgpe.w[:-1]
                        temp = temp + rank_loss

                    df.loc[len(df)] = temp + [id, rank[j]] + [knob_num] + knob_feature + [i]
                id = id + 1

    df.to_csv("{}_train_data.csv".format(test_workload))
    df = pd.read_csv("{}_train_data.csv".format(test_workload), index_col=[0])
    from sklearn.model_selection import GroupShuffleSplit
    gss = GroupShuffleSplit(test_size=.10, n_splits=1, random_state=7).split(df, groups=df['id'])
    X_train_inds, X_test_inds = next(gss)

    train_data = df.iloc[X_train_inds]
    X_train = train_data.loc[:, ~train_data.columns.isin(['id', 'rank'])]
    y_train = train_data.loc[:, train_data.columns.isin(['rank'])]
    groups = train_data.groupby('id').size().to_frame('size')['size'].to_numpy()

    test_data = df.iloc[X_test_inds]
    # We need to keep the id for later predictions
    X_test = test_data.loc[:, ~test_data.columns.isin(['rank'])]
    y_test = test_data.loc[:, test_data.columns.isin(['id', 'rank'])]



    import xgboost as xgb

    model = xgb.XGBRanker(
        #tree_method='gpu_hist',
        booster='gbtree',
        objective='rank:pairwise',
        random_state=42,
        learning_rate=0.1,
        colsample_bytree=0.9,
        eta=0.05,
        max_depth=6,
        n_estimators=110,
        subsample=0.75
    )

    model.fit(X_train, y_train, group=groups, verbose=True)


    def predict(model, df):
        return model.predict(df.loc[:, ~df.columns.isin(['id'])]).tolist()


    predictions = (X_test.groupby('id')
                   .apply(lambda x: predict(model, x)))
    true_rank = test_data.loc[:, test_data.columns.isin(['id','rank'])].groupby('id')['rank'].apply(list)
    from sklearn.metrics import ndcg_score
    import numpy as np
    print(ndcg_score(true_rank.values.tolist(), predictions.values.tolist()))
    model.save_model("xgboost_test_{}.json".format(test_workload))