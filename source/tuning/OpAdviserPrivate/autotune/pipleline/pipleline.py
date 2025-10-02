# License: MIT

import os
import abc
import numpy as np
import sys
import time
import traceback
import math
import random
import pickle
import pandas as pd
from typing import List
import xgboost as xgb
import json
from collections import OrderedDict, defaultdict
from tqdm import tqdm
from autotune.utils.util_funcs import check_random_state
from autotune.utils.logging_utils import get_logger
from autotune.utils.history_container import HistoryContainer, MOHistoryContainer
from autotune.utils.constants import MAXINT, SUCCESS
from autotune.utils.samplers import SobolSampler, LatinHypercubeSampler
from autotune.utils.multi_objective import get_chebyshev_scalarization, NondominatedPartitioning
from autotune.utils.config_space.util import convert_configurations_to_array, impute_incumb_values, max_min_distance
from autotune.utils.history_container import Observation
from autotune.pipleline.base import BOBase
from autotune.utils.constants import MAXINT, SUCCESS, FAILED, TIMEOUT
from autotune.utils.limit import time_limit, TimeoutException, no_time_limit_func
from autotune.utils.util_funcs import get_result
from autotune.utils.config_space import ConfigurationSpace
from autotune.utils.config_space.space_utils import estimate_size, get_space_feature
from autotune.selector.selector import KnobSelector
from autotune.optimizer.surrogate.core import build_surrogate, surrogate_switch
from autotune.optimizer.core import build_acq_func, build_optimizer
from autotune.transfer.tlbo.rgpe import RGPE
from autotune.utils.util_funcs import check_random_state
from autotune.utils.config_space import ConfigurationSpace, UniformIntegerHyperparameter, CategoricalHyperparameter, UniformFloatHyperparameter
from autotune.optimizer.ga_optimizer import GA_Optimizer
from autotune.optimizer.bo_optimizer import BO_Optimizer
from autotune.optimizer.ddpg_optimizer import DDPG_Optimizer
import pdb
from autotune.knobs import ts, logger

class PipleLine(BOBase):
    """
    Basic Advisor Class, which adopts a policy to sample a configuration.
    """

    def __init__(self, objective_function: callable,
                 config_space,
                 num_objs,
                 num_constraints=0,
                 optimizer_type='MBO',
                 sample_strategy: str = 'bo',
                 max_runs=200,
                 runtime_limit=None,
                 time_limit_per_trial=180,
                 surrogate_type='auto',
                 acq_type='auto',
                 acq_optimizer_type='auto',
                 initial_runs=3,
                 init_strategy='random_explore_first',
                 initial_configurations=None,
                 ref_point=None,
                 history_bo_data: List[OrderedDict] = None,
                 logging_dir='logs',
                 task_id='default_task_id',
                 random_state=np.random.RandomState(42),
                 selector_type='shap',
                 incremental='decrease',
                 incremental_every=4,
                 incremental_num=1,
                 num_hps_init=5,
                 num_metrics=65,
                 space_transfer=False,
                 knob_config_file=None,
                 auto_optimizer=False,
                 auto_optimizer_type='learned',
                 hold_out_workload=None,
                 history_workload_data=None,
                 only_knob = False,
                 only_range = False,
                 advisor_kwargs: dict = None,
                 #  latent_dim=0,
                 #2024-12-06 softmax transformer
                 softmax_weight=True,
                 transformer=True,
                 #2024-12-06 softmax transformer
                 **kwargs
                 ):


        super().__init__(objective_function, config_space, task_id=task_id, logging_dir=logging_dir,
                         random_state=random_state, initial_runs=initial_runs, max_runs=max_runs,
                         runtime_limit=runtime_limit, sample_strategy=sample_strategy,
                         time_limit_per_trial=time_limit_per_trial, surrogate_type=surrogate_type, history_bo_data=history_bo_data)

        self.num_objs = num_objs
        self.num_constraints = num_constraints
        self.FAILED_PERF = [MAXINT] * self.num_objs

        self.selector_type = selector_type
        self.optimizer_type = optimizer_type
        self.config_space_all = config_space
        self.incremental = incremental  # none, increase, decrease
        self.incremental_every = incremental_every  # how often increment the number of knobs
        self.incremental_num = incremental_num  # how many knobs to increment each time
        self.num_hps_max = len(self.config_space_all.get_hyperparameters())
        self.num_hps_init = num_hps_init if not num_hps_init == -1 else self.num_hps_max
        self.num_metrics = num_metrics
        self.selector = KnobSelector(self.selector_type)
        self.random_state = random_state
        self.current_context = None
        self.space_transfer = space_transfer
        self.only_knob = only_knob
        self.only_range = only_range
        self.knob_config_file = knob_config_file
        self.auto_optimizer = auto_optimizer
        if space_transfer or auto_optimizer:
            self.space_step_limit = 3
            self.space_step = 0

        if self.space_transfer:
        # 2024-11-20: ground truth
        # if True:
        # 2024-11-20: ground truth
            self.initial_configurations = self.get_max_distence_best()

        if auto_optimizer:
            self.auto_optimizer_type = auto_optimizer_type
            if auto_optimizer_type == 'learned':
                self.source_workloadL = ['sysbench', 'twitter', 'job', 'tpch']
                self.source_workloadL.remove(hold_out_workload)
                self.ranker = xgb.XGBRanker(
                # tree_method='gpu_hist',
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
                self.ranker.load_model("tools/xgboost_test_{}.json".format(hold_out_workload))
                self.history_workload_data =  history_workload_data
            elif auto_optimizer_type == 'best':
                # self.best_method_id_list = [3] * 50 + [1] * 150
                with open("tools/{}_best_optimizer.pkl".format(hold_out_workload), 'rb') as f:
                    self.best_method_id_list = pickle.load(f)

        # self.logger.info("Total space size:{}".format(estimate_size(self.config_space, 'scripts/experiment/gen_knobs/mysql_all_197_32G.json')))
        self.iter_begin_time = time.time()
        advisor_kwargs = advisor_kwargs or {}
        # init history container
        if self.num_objs == 1:
            self.history_container = HistoryContainer(task_id=self.task_id,
                                                      num_constraints=self.num_constraints,
                                                      config_space=self.config_space)
            #2024-11-11: code for experiment
            # self.history_container2 = HistoryContainer(task_id=f'{self.task_id}_ground_truth2',
            #                                           num_constraints=self.num_constraints,
            #                                           config_space=self.config_space2)
            #2024-11-11: code for experiment
        else:
            self.history_container = MOHistoryContainer(task_id=self.task_id,
                                                        num_objs=self.num_objs,
                                                        num_constraints=self.num_constraints,
                                                        config_space=self.config_space,
                                                        ref_point=ref_point)
        # load history container if exists
        self.load_history()
        if not self.auto_optimizer:
            if optimizer_type in ('MBO', 'SMAC', 'auto'):
                self.optimizer = BO_Optimizer(config_space,
                                              self.history_container,
                                              num_objs=self.num_objs,
                                              num_constraints=num_constraints,
                                              initial_trials=initial_runs,
                                              init_strategy=init_strategy,
                                              initial_configurations=initial_configurations,
                                              surrogate_type=surrogate_type,
                                              acq_type=acq_type,
                                              acq_optimizer_type=acq_optimizer_type,
                                              ref_point=ref_point,
                                              history_bo_data=history_bo_data,
                                              random_state=random_state,
                                            #   latent_dim=latent_dim,
                                              **advisor_kwargs)
                #2024-11-11: code for experiment
                # self.optimizer2 = BO_Optimizer(config_space,
                #                               self.history_container2,
                #                               num_objs=self.num_objs,
                #                               num_constraints=num_constraints,
                #                               initial_trials=initial_runs,
                #                               init_strategy=init_strategy,
                #                               initial_configurations=initial_configurations,
                #                               surrogate_type=surrogate_type,
                #                               acq_type=acq_type,
                #                               acq_optimizer_type=acq_optimizer_type,
                #                               ref_point=ref_point,
                #                               history_bo_data=history_bo_data,
                #                               random_state=random_state,
                #                             #   latent_dim=latent_dim,
                #                               **advisor_kwargs)
                #2024-11-11: code for experiment

            elif optimizer_type == 'TPE':
                assert self.num_objs == 1 and num_constraints == 0

                from autotune.optimizer.tpe_optimizer import TPE_Optimizer
                self.optimizer = TPE_Optimizer(config_space,
                                               **advisor_kwargs)
            elif optimizer_type == 'GA':
                assert self.num_objs == 1 and num_constraints == 0
                assert self.incremental == 'none'
                self.optimizer = GA_Optimizer(config_space,
                                              self.history_container,
                                              num_objs=self.num_objs,
                                              num_constraints=num_constraints,
                                              output_dir=logging_dir,
                                              random_state=random_state,
                                              **advisor_kwargs)
            elif optimizer_type == 'TurBO':
                # TODO: assertion? warm start?
                assert self.num_objs == 1 and num_constraints == 0
                assert self.incremental == 'none'
                from autotune.optimizer.turbo_optimizer import TURBO_Optimizer
                self.optimizer = TURBO_Optimizer(config_space,
                                                 initial_trials=initial_runs,
                                                 init_strategy=init_strategy,
                                                 **advisor_kwargs)
            elif optimizer_type == 'DDPG':
                assert self.num_objs == 1 and num_constraints == 0
                assert self.incremental == 'none'
                self.optimizer = DDPG_Optimizer(config_space,
                                                self.history_container,
                                                metrics_num=num_metrics,
                                                task_id=task_id,
                                                params=kwargs['params'],
                                                batch_size=kwargs['batch_size'],
                                                mean_var_file=kwargs['mean_var_file']
                                                #2024-12-06 softmax transformer
                                                ,transformer=transformer,
                                                #2024-12-06 softmax transformer
                                                )
            else:
                raise ValueError('Invalid advisor type!')
        else:
            SMAC = BO_Optimizer(config_space,
                                self.history_container,
                                num_objs=self.num_objs,
                                num_constraints=num_constraints,
                                initial_trials=initial_runs,
                                init_strategy=init_strategy,
                                initial_configurations=initial_configurations,
                                surrogate_type='prf',
                                acq_type=acq_type,
                                acq_optimizer_type=acq_optimizer_type,
                                ref_point=ref_point,
                                history_bo_data=history_bo_data,
                                random_state=random_state,
                                            #   latent_dim=latent_dim,
                                **advisor_kwargs)
            MBO = BO_Optimizer(config_space,
                               self.history_container,
                               num_objs=self.num_objs,
                               num_constraints=num_constraints,
                               initial_trials=initial_runs,
                               init_strategy=init_strategy,
                               initial_configurations=initial_configurations,
                               surrogate_type='gp',
                               acq_type=acq_type,
                               acq_optimizer_type=acq_optimizer_type,
                               ref_point=ref_point,
                               history_bo_data=history_bo_data,
                               random_state=random_state,
                                            #   latent_dim=latent_dim,
                               **advisor_kwargs)

            GA = GA_Optimizer(config_space,
                              self.history_container,
                              num_objs=self.num_objs,
                              num_constraints=num_constraints,
                              output_dir=logging_dir,
                              random_state=random_state,
                              **advisor_kwargs)
            DDPG = DDPG_Optimizer(config_space,
                                  self.history_container,
                                  metrics_num=num_metrics,
                                  task_id=task_id,
                                  params=kwargs['params'],
                                  batch_size=kwargs['batch_size'],
                                  mean_var_file=kwargs['mean_var_file']
                                    #2024-12-06 softmax transformer
                                    ,transformer=transformer,
                                    #2024-12-06 softmax transformer
                                  )
            self.optimizer_list = [SMAC, MBO, DDPG, GA]
            self.optimizer = SMAC
        self.tuning_result=list()
        self.max_iterations=self.iteration_id+1
        #2024-12-06 softmax transformer
        self.softmax_weight=softmax_weight
        self.transformer=transformer
        #2024-12-06 softmax transformer


    def get_max_distence_best(self):
        default_config = self.config_space.get_default_configuration()
        candidate_configs = list()
        for  history_container in self.history_bo_data:
            if len(history_container.incumbents):
                candidate_configs.append(history_container.incumbents[0][0])

        return  max_min_distance(default_config=default_config, src_configs=candidate_configs, num=self.init_num)

    def get_history(self):
        return self.history_container
        #2024-11-11: code for experiment
        # return self.history_container,self.history_container2
        #2024-11-11: code for experiment

    def get_incumbent(self):
        return self.history_container.get_incumbents()


    def run(self):
        compact_space = self.config_space
        #2024-11-11: code for experiment
        # compact_space2=  None
        #2024-11-11: code for experiment
        for _ in tqdm(range(self.iteration_id, self.max_iterations)):
            if self.budget_left < 0:
                self.logger.info('Time %f elapsed!' % self.runtime_limit)
                break
            time_b = time.time()
            start_time = time.time()
            # get another compact space
            if (self.space_transfer or self.auto_optimizer) and (self.space_step >= self.space_step_limit):
                self.space_step_limit = 3
                self.space_step = 0
                if self.space_transfer:
                    f = open('space.record','a')
                    time_b = time.time()
                    compact_space = self.get_compact_space()
                    #2024-11-11: code for experiment
                    # compact_space,compact_space2=  self.get_compact_space()
                    #2024-11-11: code for experiment
                    f.write(str(time.time() - time_b)+'\n')
                    f.close()

                if self.auto_optimizer:
                    f = open('optimizer.record', 'a')
                    time_b = time.time()
                    self.optimizer = self.select_optimizer(type=self.auto_optimizer_type, space=self.config_space if compact_space is None else compact_space)
                    f.write(str(time.time() - time_b) + '\n')
                    f.close()

                time_b = time.time()

                if self.space_transfer and not compact_space == self.optimizer.config_space:
                    if isinstance(self.optimizer, GA_Optimizer):
                        self.optimizer = GA_Optimizer(compact_space,
                                                      self.history_container,
                                                      num_objs=self.num_objs,
                                                      num_constraints=self.num_constraints,
                                                      output_dir=self.optimizer.output_dir,
                                                      random_state=self.random_state)
                        if self.auto_optimizer:
                            self.optimizer_list[-1] = self.optimizer

                    if isinstance(self.optimizer, DDPG_Optimizer):
                        self.optimizer = DDPG_Optimizer(compact_space,
                                                        self.history_container,
                                                        metrics_num=self.num_metrics,
                                                        task_id=self.history_container.task_id,
                                                        params=self.optimizer.params,
                                                        batch_size=self.optimizer.batch_size,
                                                        mean_var_file=self.optimizer.mean_var_file
                                                        #2024-12-06 softmax transformer
                                                        ,transformer=self.transformer,
                                                        #2024-12-06 softmax transformer
                                    )
                        if self.auto_optimizer:
                            self.optimizer_list[-2] = self.optimizer


            if self.space_transfer:
                space = compact_space if not compact_space is None else self.config_space
                self.logger.info("[Iteration {}] [{},{}] Total space size:{}".format(self.iteration_id,self.space_step , self.space_step_limit, estimate_size(space, self.knob_config_file)))


            f = open('all.record', 'a')
            config, _, _, objs,latL = self.iterate(compact_space)
            self.tuning_result.append((objs,config))
            #2024-11-11: code for experiment
            # _ , _, _, objs,_ , _, _, objs2 = self.iterate(compact_space,compact_space2)
            #2024-11-11: code for experiment
            f.write(str(time.time() - time_b) + '\n')
            f.close()

            # determine whether explore one more step in the space
            if (self.space_transfer or self.auto_optimizer) and  len(self.history_container.get_incumbents()) > 0 and objs[0] < self.history_container.get_incumbents()[0][1]:
                self.space_step_limit += 1

            self.save_history()
            runtime = time.time() - start_time
            self.budget_left -= runtime
            # recode the step in the space
            if self.space_transfer or self.auto_optimizer:
                self.space_step += 1

        return self.get_history()

    def knob_selection(self):
        assert self.num_objs == 1

        if self.iteration_id < self.init_num and not self.incremental == 'increase':
            return

        if self.incremental == 'none':
            if self.num_hps_init == -1 or self.num_hps_init == len(self.config_space.get_hyperparameter_names()):
                return

            new_config_space, _ = self.selector.knob_selection(
                self.config_space_all, self.history_container, self.num_hps_init)
            #2024-11-11: code for experiment
            # new_config_space2, _ = self.selector.knob_selection(
            #     self.config_space_all, self.history_container2, self.num_hps_init)
            #2024-11-11: code for experiment

            if not self.config_space == new_config_space:
                logger.info("new configuration space: {}".format(new_config_space))
                self.history_container.alter_configuration_space(new_config_space)
                self.config_space = new_config_space
                #2024-11-11: code for experiment
                # self.history_container2.alter_configuration_space(new_config_space2)
                # self.config_space2 = new_config_space2
                #2024-11-11: code for experiment

        else:
            incremental_step = int( max(self.iteration_id - self.init_num, 0 )/self.incremental_every)
            if self.incremental == 'increase':
                num_hps = self.num_hps_init + incremental_step * self.incremental_every
                num_hps = min(num_hps, self.num_hps_max)
                self.logger.info("['increase'] tune {} knobs".format(num_hps))
                if not num_hps  == len(self.config_space.get_hyperparameter_names()) or self.iteration_id == self.init_num:
                    self.knob_rank = list(json.load(open(self.knob_config_file)).keys())
                    #_, self.knob_rank = self.selector.knob_selection(self.config_space_all, self.history_container, self.num_hps_max)
                    new_config_space = ConfigurationSpace()
                    for knob in self.knob_rank[:num_hps]:
                        new_config_space.add_hyperparameter(self.config_space_all.get_hyperparameter(knob) )
                    logger.info("new configuration space: {}".format(new_config_space))
                    self.history_container.alter_configuration_space(new_config_space)
                    self.config_space = new_config_space

            elif self.incremental == 'decrease':
                num_hps = int(self.num_hps_init * (0.6 **  incremental_step)) #- incremental_step * self.incremental_every
                num_hps = max(num_hps, 5)
                self.logger.info("['decrease'] tune {} knobs".format(num_hps))
                if not num_hps == len(self.config_space.get_hyperparameter_names()):
                    _, self.knob_rank = self.selector.knob_selection(self.config_space_all, self.history_container, self.num_hps_max)
                    new_config_space = ConfigurationSpace()
                    for knob in self.knob_rank[:num_hps]:
                        new_config_space.add_hyperparameter(self.config_space_all.get_hyperparameter(knob))

                    # # fix the knobs that no more to tune
                    # inc_config = self.history_container.incumbents[0][0]
                    # self.objective_function(inc_config)

                    logger.info("new configuration space: {}".format(new_config_space))
                    self.history_container.alter_configuration_space(new_config_space)
                    self.config_space = new_config_space

    def select_optimizer(self, space, type='learned'):
        optimizer_name = [ 'smac', 'mbo', 'ddpg', 'ga']
        if type == 'random':
            idx = random.choices([i for i in range(len(self.optimizer_list))])[0]
            self.logger.info("select {}".format(optimizer_name[idx]))
            return self.optimizer_list[idx]

        if type == 'two_phase':
            if self.iteration_id < 140:
                idx = -1
            else:
                idx = -2
            self.logger.info("select {}".format(optimizer_name[idx]))
            return self.optimizer_list[idx]


        if type == 'best':
            idx = self.best_method_id_list[self.iteration_id]
            self.logger.info("select {}".format(optimizer_name[idx]))
            return self.optimizer_list[idx]

        if self.iteration_id < self.init_num:
            self.logger.info("select {}".format(optimizer_name[0]))
            return self.optimizer_list[0]
        
        # feature needed: smac, mbo, ddpg, ga, sysbench, twitter, tpch, target, knob_num, integer, enum, iteration
        if not hasattr(self, 'rgpe_op'):
            rng = check_random_state(100)
            seed = 42
            self.rgpe_op = RGPE(self.config_space, self.history_workload_data, 42, num_src_hpo_trial=-1, only_source=False)

        feature_name = optimizer_name + self.source_workloadL + ['target', 'knob_num', 'integer', 'enum', 'iteration']
        df = pd.DataFrame(columns=feature_name)
        rank_loss_list = self.rgpe_op.get_ranking_loss(self.history_container)
        config_feature = get_space_feature(space)
        for i in range(4):
            temp = [0] * 4
            temp[i] = 1
            df.loc[len(df)] = temp + rank_loss_list + config_feature + [self.iteration_id]

        rank = self.ranker.predict(df)
        idx = np.argmin(rank)
        self.logger.info("[learned] select {}".format(optimizer_name[idx]))
        return self.optimizer_list[idx]


    def iterate(self, compact_space=None
        #2024-11-11: code for experiment
        # ,compact_space2=None,
        #2024-11-11: code for experiment                
                ):
        self.knob_selection()
        #get configuration suggestion
        if self.space_transfer and len(self.history_container.configurations) < self.init_num:
            #space transfer: use best source config to init
            config = self.initial_configurations[len(self.history_container.configurations)]
        #2024-11-11: code for experiment
        # if self.space_transfer and len(self.history_container2.configurations) < self.init_num:
        #     #space transfer: use best source config to init
        #     config2 = self.initial_configurations[len(self.history_container2.configurations)]
        #2024-11-11: code for experiment
        else:
            config = self.optimizer.get_suggestion(history_container=self.history_container, compact_space=compact_space)
            #2024-11-11: code for experiment
            # config2 = self.optimizer2.get_suggestion(history_container=self.history_container2, compact_space=compact_space2)
            #2024-11-11: code for experiment
        if self.space_transfer:
            if len(self.history_container.get_incumbents()):
                config = impute_incumb_values(config, self.history_container.get_incumbents()[0][0])
            #2024-11-11: code for experiment
            # if len(self.history_container2.get_incumbents()):
            #     config2 = impute_incumb_values(config2, self.history_container2.get_incumbents()[0][0])
            #2024-11-11: code for experiment
                config_space = self.history_container.get_incumbents()[0][0].configuration_space
            else:
                config = impute_incumb_values(config, self.config_space.get_default_configuration())
                config_space = self.config_space.get_default_configuration().configuration_space
            if isinstance(self.optimizer, DDPG_Optimizer):
                self.optimizer = DDPG_Optimizer(config_space,
                                                self.history_container,
                                                metrics_num=self.num_metrics,
                                                task_id=self.history_container.task_id,
                                                params=self.optimizer.params,
                                                batch_size=self.optimizer.batch_size,
                                                mean_var_file=self.optimizer.mean_var_file
                                                #2024-12-06 softmax transformer
                                                ,transformer=self.transformer,
                                                #2024-12-06 softmax transformer
                                                )
        _, trial_state, constraints, objs,latL = self.evaluate(config)
        #2024-11-11: code for experiment
        # _, trial_state, constraints, objs,_, trial_state2, constraints2, objs2 = self.evaluate(config,config2)
        #2024-11-11: code for experiment
        
        return config, trial_state, constraints, objs,latL    
        #2024-11-11: code for experiment
        # return config, trial_state, constraints, objs,config2, trial_state2, constraints2, objs2
        #2024-11-11: code for experiment

    def save_history(self):
        dir_path = os.path.join('repo')
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        file_name = 'history_%s.json' % self.task_id
        return self.history_container.save_json(os.path.join(dir_path, file_name))
        #2024-11-11: code for experiment
        # return (
        #     self.history_container.save_json(os.path.join(dir_path, file_name)),
        #     self.history_container2.save_json(os.path.join(dir_path, f'history_{self.task_id}_ground_truth2.json')),
        #     )
        #2024-11-11: code for experiment


    def load_history(self):
        # TODO: check info
        fn = os.path.join('repo', 'history_%s.json' % self.task_id)
        if not os.path.exists(fn):
            self.logger.info('Start new DBTune task')
        else:
            self.history_container.load_history_from_json(fn)
            self.iteration_id = len(self.history_container.configurations)
            if self.space_transfer:
                self.space_step = self.space_step_limit
            self.logger.info('Load {} iterations from {}'.format(self.iteration_id, fn))
        #2024-11-11: code for experiment
        # fn = os.path.join('repo', 'history_%s_ground_truth2.json' % self.task_id)
        # if not os.path.exists(fn):
        #     self.logger.info('Start new DBTune task')
        # else:
        #     self.history_container2.load_history_from_json(fn)
        #2024-11-11: code for experiment


    def reset_context(self, context):
        self.current_context = context
        self.optimizer.current_context = context
        if self.optimizer.surrogate_model:
            self.optimizer.surrogate_model.current_context =  context

    def evaluate(self, config
        #2024-11-11: code for experiment
        # ,config2,
        #2024-11-11: code for experiment   
        ):
        iter_time = time.time() - self.iter_begin_time
        trial_state = SUCCESS
        start_time = time.time()
        objs, constraints, em, resource, im, info, trial_state,latL = self.objective_function(config)
        if trial_state == FAILED :
            objs = self.FAILED_PERF

        elapsed_time = time.time() - start_time

        self.iter_begin_time = time.time()

        if self.surrogate_type == 'context_prf' and config == self.history_container.config_space.get_default_configuration():
            self.reset_context(np.array(im))

        observation = Observation(
            config=config, objs=objs, constraints=constraints,
            trial_state=trial_state, elapsed_time=elapsed_time, iter_time=iter_time, EM=em, resource=resource, IM=im, info=info, context=self.current_context
        )
        self.history_container.update_observation(observation)
        #2024-11-11: code for experiment   
        # iter_time2 = time.time() - self.iter_begin_time
        # objs2, constraints2, em2, resource2, im2, info2, trial_state2 = self.objective_function(config2)
        # if trial_state2 == FAILED :
        #     objs2 = self.FAILED_PERF

        # elapsed_time2 = time.time() - elapsed_time

        # self.iter_begin_time = time.time()
        
        # observation2 = Observation(
        #     config=config2, objs=objs2, constraints=constraints2,
        #     trial_state=trial_state2, elapsed_time=elapsed_time2, iter_time=iter_time2, EM=em2, resource=resource2, IM=im2, info=info2, context=self.current_context
        # )
        # self.history_container2.update_observation(observation2)
        #2024-11-11: code for experiment   

        if self.optimizer_type in ['GA', 'TurBO', 'DDPG'] and not self.auto_optimizer:
            if  not self.optimizer_type == 'DDPG' or not trial_state == FAILED:
                self.optimizer.update(observation)

        if not trial_state == FAILED and self.auto_optimizer and not self.space_transfer:
            self.optimizer_list[2].update(observation)
            self.optimizer_list[3].update(observation)

        self.iteration_id += 1
        # Logging.
        if self.num_constraints > 0:
            self.logger.info('Iteration %d, objective value: %s, constraints: %s.'
                             % (self.iteration_id, objs, constraints))
        else:
            #self.logger.info('Iteration %d, objective value: %s ,improvement,: :.2%' % (self.iteration_id, objs, (objs-self.default_obj))/self.default_obj)
            self.logger.info('Iteration %d, objective value: %s.' % (self.iteration_id, objs))
        return config, trial_state, constraints, objs,latL
        #2024-11-11: code for experiment   
        # return config, trial_state, constraints, objs,config2, trial_state2, constraints2, objs2
        #2024-11-11: code for experiment   


    def get_compact_space(self):
#2024-11-11: code for experiment
        # with open(
        #     f"repo_backup/history_{self.task_id}_ground_truth.json"
        # ) as f:
        #     ground_truth = sorted(json.load(f)["data"], key=lambda x: x["external_metrics"].get("tps", 0))[-1]['configuration']
#2024-11-11: code for experiment
        if not hasattr(self, 'rgpe'):
            rng = check_random_state(100)
            seed = 42
            self.rgpe = RGPE(self.config_space, self.history_bo_data, 42, num_src_hpo_trial=-1, only_source=False)

        rank_loss_list = self.rgpe.get_ranking_loss(self.history_container)
        similarity_list = [1 - i for i in rank_loss_list]

        #2024-12-06 softmax transformer
        with open(f'{self.task_id}_similarity_list','a')as f:
            f.write(f'''{similarity_list}
''')
        #2024-12-06 softmax transformer

        ### filter unsimilar task
        sample_list = list()
        similarity_threhold = np.quantile(similarity_list, 0.5)
        candidate_list, weight = list(), list()
        surrogate_list = self.history_bo_data + [self.history_container]
        #2024-12-06 softmax transformer
        softmax_weight=list()
        #2024-12-06 softmax transformer
        for i in range(len(surrogate_list)):
            if similarity_list[i] > similarity_threhold:
                candidate_list.append(i)
                weight.append(similarity_list[i] / sum(similarity_list))
                #2024-12-06 softmax transformer
                softmax_weight.append(similarity_list[i])
                #2024-12-06 softmax transformer
        if not len(candidate_list):
            self.logger.info("Remain the space:{}".format(self.config_space))
            return self.config_space

        ### determine the number of sampled task
        if len(surrogate_list) > 60:
            k = int(len(surrogate_list) / 10)
        else:
            k = 6

        k = min(k, len(candidate_list))

        # sample k task s
        for j in range(k):
            item = random.choices(candidate_list, weights=weight, k=1)[0]
            sample_list.append(item)
            del (weight[candidate_list.index(item)])
            candidate_list.remove(item)

        if not len(surrogate_list) - 1 in sample_list:
            sample_list.append(len(surrogate_list) - 1)

        # obtain the pruned space for the sampled tasks
        important_dict = defaultdict(int)
        pruned_space_list = list()
        quantile_min = 1 / 1e9
        quantile_max = 1 - 1 / 1e9
        for j in range(len(surrogate_list)):
            #2024-12-06 softmax transformer
            # if not j in sample_list:
            #     continue
            #2024-12-06 softmax transformer
            quantile = quantile_max - (1 - 2 * max(similarity_list[j] - 0.5, 0)) * (quantile_max - quantile_min)
            ys_source = - surrogate_list[j].get_transformed_perfs()
            performance_threshold = np.quantile(ys_source, quantile)
            default_performance = - surrogate_list[j].get_default_performance()
            self.logger.info("[{}] similarity:{} default:{}, quantile:{}, threshold:{}".format(surrogate_list[j].task_id, similarity_list[j], default_performance, quantile, performance_threshold))
            if performance_threshold < default_performance:
                quantile = 0

            pruned_space = surrogate_list[j].get_promising_space(quantile)
            self.logger.info(pruned_space)
            pruned_space_list.append(pruned_space)
            #code for error case analysis
            if not j in sample_list:
                continue
            #code for error case analysis
            total_imporve = sum([pruned_space[key][2] for key in list(pruned_space.keys())])
            for key in pruned_space.keys():
                if not pruned_space[key][0] == pruned_space[key][1]:
                    if pruned_space[key][2] > 0.01 or pruned_space[key][2] > 0.1 * total_imporve:
                        # print((key,pruned_space[key] ))
                        important_dict[key] = important_dict[key] + similarity_list[j] / sum(
                            [similarity_list[i] for i in sample_list])

        #2024-12-06 softmax transformer
        with open(f'{self.task_id}_sample_list','a')as f:
            f.write(f'''{sample_list}
''')
        #2024-12-06 softmax transformer

#code for error case analysis
#         with open(
#             f"repo/history_{self.task_id}_ground_truth.json"
#         ) as f:
#             j = json.load(f)["data"]
#             c = sorted(j, key=lambda x: x["external_metrics"].get("tps", 0))[-1]['configuration']
#         mask=np.ones(len(pruned_space_list),bool)
#         mask[sample_list]=False
#
#         knobs=np.zeros(len(pruned_space_list))
#         for k in c:
#             knob=self.config_space_all.get_hyperparameters_dict()[k]
#             transform = knob._transform
#             for i in range(len(pruned_space_list)):
#                 space=pruned_space_list[i]
#                 s=space[k]
#                 if isinstance(knob,CategoricalHyperparameter):
#                     if c[k] in s[0]:
#                         knobs[i]+=1
#                 else:
#                     if transform(s[0])<=c[k]<=transform(s[1]):
#                         knobs[i]+=1
#         sampled=knobs[sample_list]
#         not_sampled=knobs[mask]
#         sl=np.array(similarity_list)
#         st=''
#         st+=(f'''s="{self.task_id}"
# ''')
#         st+=(f'''sampled_similarities={sl[sample_list].tolist()}
# ''')
#         st+=(f'''sampled_spaces={sampled.tolist()}
# ''')
#         st+=(f'''not_sampled_similarities={sl[mask].tolist()}
# ''')
#         st+=(f'''not_sampled_spaces={not_sampled.tolist()}
# ''')
#         effective_regions_x={}
#         effective_regions_y={}
#         for k in c:
#             if pruned_space_list[0][k][1] is None:
#                 continue
#             index_list = set()
#             for space in pruned_space_list:
#                 info = space[k]
#                 if not info[0] == info[1]:
#                     index_list.add(info[0])
#                     index_list.add(info[1])
#             index_list = sorted(index_list)
#             count_array = np.array([index_list[:-1], index_list[1:]]).T
#             count_array = np.hstack((count_array, np.zeros((count_array.shape[0], 1))))
#             for space in pruned_space_list:
#                 if not info[0] == info[1]:
#                     for i in range(count_array.shape[0]):
#                         if count_array[i][0] >= info[0] and count_array[i][1] <= info[1]:
#                             count_array[i][2] += 1
#             effective_regions_x[k]=[]
#             effective_regions_y[k]=[]
#             for i in range(count_array.shape[0]):
#                 effective_regions_x[k].append(count_array[i][0])
#                 effective_regions_x[k].append(count_array[i][1])
#                 effective_regions_y[k].append(count_array[i][2])
#                 effective_regions_y[k].append(count_array[i][2])
#         st+=(f'''effective_regions_x={effective_regions_x}
# ''')
#         st+=(f'''effective_regions_y={effective_regions_y}
# ''')
#code for error case analysis

        # remove unimportant knobs
        if self.only_range:
            important_knobs =  self.config_space.get_hyperparameter_names()
        else:
            important_knobs = list()
            for key in important_dict.keys():
                if important_dict[key] >= 0:
                    important_knobs.append(key)

        if self.only_knob:
            target_space = ConfigurationSpace()
            for knob in important_knobs:
                target_space.add_hyperparameter(self.config_space.get_hyperparameters_dict()[knob])
            self.logger.info(target_space)
            return target_space

        # generate target pruned space
        default_array = self.config_space.get_default_configuration().get_array()
        default_knobs = self.config_space.get_hyperparameter_names()
        target_space = ConfigurationSpace()

#code for error case analysis
#         ik=np.zeros(len(pruned_space_list))
#         for k in important_knobs:
#             knob=self.config_space_all.get_hyperparameters_dict()[k]
#             transform = knob._transform
#             for i in range(len(pruned_space_list)):
#                 space=pruned_space_list[i]
#                 s=space[k]
#                 if isinstance(knob,CategoricalHyperparameter):
#                     if c[k] in s[0]:
#                         ik[i]+=1
#                 else:
#                     if transform(s[0])<=c[k]<=transform(s[1]):
#                         ik[i]+=1
#         # not_sampled=ik[mask]
#         st+=(f'''sampled_spaces_scaled={(sampled/len(c)).tolist()}
# ''')
#         st+=(f'''sampled_important_spaces={(ik[sample_list]/len(important_knobs)).tolist()}
# ''')
# #         st+=(f'''not_sampled_important_spaces={not_sampled.tolist()}
# # ''')
        pruned_space_list=np.array(pruned_space_list)[sample_list].tolist()
#         count_arrays={}
#         count_arrays2={}
#         values_dicts={}
#code for error case analysis
#2024-11-11: code for experiment
        # target_space2=ConfigurationSpace()
#2024-11-11: code for experiment
        for knob in important_knobs:
            # CategoricalHyperparameter
            if isinstance(self.config_space.get_hyperparameters_dict()[knob], CategoricalHyperparameter):
#code for error case analysis
                # values_dicts[knob]=0
#code for error case analysis
                values_dict = defaultdict(int)
                for space in pruned_space_list:
                    values = space[knob][0]
                    for v in values:
                        values_dict[v] += similarity_list[sample_list[pruned_space_list.index(space)]] / sum(
                            [similarity_list[t] for t in sample_list])
#code for error case analysis
                # values_dicts[knob]=values_dict[c[k]]
#code for error case analysis

                feasible_value = list()
                for v in values_dict.keys():
                    if values_dict[v] > 1/3:
                        feasible_value.append(v)

                if len(feasible_value) > 1:
                    default = self.config_space.get_default_configuration()[knob]
                    if not default in feasible_value:
                        default = feasible_value[0]

                    knob_add = CategoricalHyperparameter(knob, feasible_value, default_value=default)
                    target_space.add_hyperparameter(knob_add)
#2024-11-11: code for experiment
                # if ground_truth[knob] not in feasible_value:
                #     feasible_value.pop(random.randint(0,len(feasible_value)-1))
                #     feasible_value.append(ground_truth[knob])
                #     if len(feasible_value) > 1:
                #         default = self.config_space.get_default_configuration()[knob]
                #         if not default in feasible_value:
                #             default = feasible_value[0]

                #         knob_add = CategoricalHyperparameter(knob, feasible_value, default_value=default)
                #         target_space2.add_hyperparameter(knob_add)
#2024-11-11: code for experiment
                continue

            # Integer
            index_list = set()
            for space in pruned_space_list:
                info = space[knob]
                if not info[0] == info[1]:
                    index_list.add(info[0])
                    index_list.add(info[1])
            index_list = sorted(index_list)
            count_array = np.array([index_list[:-1], index_list[1:]]).T
            count_array = np.hstack((count_array, np.zeros((count_array.shape[0], 1))))
            for space in pruned_space_list:
                info = space[knob]
                if not info[0] == info[1]:
                    for i in range(count_array.shape[0]):
                        if count_array[i][0] >= info[0] and count_array[i][1] <= info[1]:
                            count_array[i][2] += similarity_list[sample_list[pruned_space_list.index(space)]] / sum(
                                [similarity_list[t] for t in sample_list])

            max_index, min_index = 0, 1
#code for error case analysis
            # count_arrays[knob]=0
            # count_arrays2[knob]=count_array.tolist()
#code for error case analysis
            # vote
            for i in range(count_array.shape[0]):
                if count_array[i][2] > 1/3 :
                    if count_array[i][0] < min_index:
                        min_index = count_array[i][0]
                    if count_array[i][1] > max_index:
                        max_index = count_array[i][1]

#code for error case analysis
                # transform = self.config_space.get_hyperparameters_dict()[knob]._transform
                # if transform(count_array[i][0])<=c[knob]<=transform(count_array[i][1]):
                #     count_arrays[knob]=count_array[i][2]
#code for error case analysis
            if max_index == 0 and min_index == 1:
                continue
            default = default_array[default_knobs.index(knob)]
            if default < min_index:
                default = min_index
            if default > max_index:
                default = max_index
            transform = self.config_space.get_hyperparameters_dict()[knob]._transform
            retry = False
            try:
                knob_add = UniformIntegerHyperparameter(knob, transform(min_index), transform(max_index), transform(default))
            except:
                retry = True
            i = 1
            while retry:
                try:
                    if transform(default) - 2 * i < transform(min_index):
                        break
                    knob_add = UniformIntegerHyperparameter(knob, transform(min_index), transform(max_index), transform(default) - 2 * i )
                    i += 1
                    retry = False
                except:
                    retry = True

            if not retry:
                target_space.add_hyperparameter(knob_add)
#2024-11-11: code for experiment
                # it=self.config_space.get_hyperparameters_dict()[knob]._inverse_transform(ground_truth[knob])
                # d=it-(max_index+min_index)/2
                # lower=transform(min_index+d)
                # upper=transform(max_index+d)
                # default_value=transform(default+d)
                # if lower==upper:
                #     lower-=1
                #     upper+=1
                # retry = True
                # i = 1
                # while retry:
                #     try:
                #         if default_value - 2 * i < lower:
                #             break
                #         knob_add = UniformIntegerHyperparameter(knob, lower, upper, default_value - 2 * i )
                #         i += 1
                #         retry = False
                #     except:
                #         retry = True
                # if not retry:
                #     target_space2.add_hyperparameter(knob_add)
#2024-11-11: code for experiment

        self.logger.info(target_space)
#code for error case analysis
#         ground_truth_in_target_range=[]
#         ground_truth_not_in_target_range=[]
#         vectors_in_ground_truth=[]
#         vectors_not_in_ground_truth=[]
#         vectors={}
#         for k in target_space:
#             knob=self.config_space_all.get_hyperparameters_dict()[k]
#             transform = knob._transform
#             t=target_space[k]
#             vector=knob._inverse_transform(c[k])
#             if isinstance(knob,CategoricalHyperparameter):
#                 if c[k] in t.choices:
#                     ground_truth_in_target_range.append(count_arrays[k])
#                     vectors_in_ground_truth.append(vector)
#                 else:
#                     ground_truth_not_in_target_range.append(count_arrays[k])
#                     vectors_not_in_ground_truth.append(vector)
#             else:
#                 if t.lower<=c[k]<=t.upper:
#                     ground_truth_in_target_range.append(count_arrays[k])
#                     vectors_in_ground_truth.append(vector)
#                 else:
#                     ground_truth_not_in_target_range.append(count_arrays[k])
#                     vectors_not_in_ground_truth.append(vector)
#             vectors[k]=vector
#         st+=(f'''ground_truth_in_target_range={ground_truth_in_target_range}
# ''')
#         st+=f'''ground_truth_not_in_target_range={ground_truth_not_in_target_range}
# '''
#         st+=f'''vectors_in_ground_truth={vectors_in_ground_truth}
# '''
#         st+=f'''vectors_not_in_ground_truth={vectors_not_in_ground_truth}
# '''
#         st+=f'''count_arrays2={count_arrays2}
# '''
#         st+=f'''vectors={vectors}
# '''
#         st+=f'''count_arrays={count_arrays}
# '''
#         print(st)
#         with open(self.task_id,'w')as f:
#             f.write(st)
#code for error case analysis
        return target_space
#2024-11-11: code for experiment
        # return target_space,target_space2
#2024-11-11: code for experiment
