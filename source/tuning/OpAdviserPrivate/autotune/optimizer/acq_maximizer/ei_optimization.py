# License: MIT
# This file is partially built on SMAC3(https://github.com/automl/SMAC3), which is licensed as follows,

# License: 3-clause BSD
# Copyright (c) 2016-2018, Ml4AAD Group (http://www.ml4aad.org/)
# Author: Aaron Klein, Marius Lindauer

import abc
import logging
import time
from typing import Iterable, List, Union, Tuple, Optional

import random
import scipy
import numpy as np
import itertools

from autotune.optimizer.acquisition_function.acquisition import AbstractAcquisitionFunction
from autotune.utils.config_space import get_one_exchange_neighbourhood, \
    Configuration, ConfigurationSpace
from autotune.utils.config_space.util import configs2space
from autotune.optimizer.acq_maximizer.random_configuration_chooser import ChooserNoCoolDown, ChooserProb
from autotune.utils.history_container import HistoryContainer, MultiStartHistoryContainer
from autotune.utils.util_funcs import get_types
from autotune.utils.constants import MAXINT


class AcquisitionFunctionMaximizer(object, metaclass=abc.ABCMeta):
    """Abstract class for acquisition maximization.

    In order to use this class it has to be subclassed and the method
    ``_maximize`` must be implemented.

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    rng : np.random.RandomState or int, optional
    """

    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rng: Union[bool, np.random.RandomState] = None
    ):
        self.logger = logging.getLogger(
            self.__module__ + "." + self.__class__.__name__
        )
        self.acquisition_function = acquisition_function
        self.config_space = config_space

        if rng is None:
            self.logger.debug('no rng given, using default seed of 42')
            self.rng = np.random.RandomState(seed=42)
        else:
            self.rng = rng

    def maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Configuration]:
        """Maximize acquisition function using ``_maximize``.

        Parameters
        ----------
        runhistory: ~autotune.utils.history_container.HistoryContainer
            runhistory object
        stats: ~autotune.stats.stats.Stats
            current stats object
        num_points: int
            number of points to be sampled
        **kwargs

        Returns
        -------
        iterable
            An iterable consisting of :class:`autotune.config_space.Configuration`.
        """
        return [t[1] for t in self._maximize(runhistory, num_points, **kwargs)]

    @abc.abstractmethod
    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        """Implements acquisition function maximization.

        In contrast to ``maximize``, this method returns an iterable of tuples,
        consisting of the acquisition function value and the configuration. This
        allows to plug together different acquisition function maximizers.

        Parameters
        ----------
        runhistory: ~autotune.utils.history_container.HistoryContainer
            runhistory object
        stats: ~autotune.stats.stats.Stats
            current stats object
        num_points: int
            number of points to be sampled
        **kwargs

        Returns
        -------
        iterable
            An iterable consistng of
            tuple(acqusition_value, :class:`autotune.config_space.Configuration`).
        """
        raise NotImplementedError()

    def _sort_configs_by_acq_value(
            self,
            configs: List[Configuration]
    ) -> List[Tuple[float, Configuration]]:
        """Sort the given configurations by acquisition value

        Parameters
        ----------
        configs : list(Configuration)

        Returns
        -------
        list: (acquisition value, Candidate solutions),
                ordered by their acquisition function value
        """

        acq_values = self.acquisition_function(configs)

        # From here
        # http://stackoverflow.com/questions/20197990/how-to-make-argsort-result-to-be-random-between-equal-values
        random = self.rng.rand(len(acq_values))
        # Last column is primary sort key!
        indices = np.lexsort((random.flatten(), acq_values.flatten()))

        # Cannot use zip here because the indices array cannot index the
        # rand_configs list, because the second is a pure python list
        return [(acq_values[ind][0], configs[ind]) for ind in indices[::-1]]


    def set_compact_space(self, space):
        self.config_space = space



class CMAESOptimizer(AcquisitionFunctionMaximizer):
    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rng: Union[bool, np.random.RandomState] = None,
            rand_prob=0.25,
    ):
        super().__init__(acquisition_function, config_space, rng)
        self.random_chooser = ChooserProb(prob=rand_prob, rng=rng)

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        raise NotImplementedError()

    def maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        try:
            from cma import CMAEvolutionStrategy
        except ImportError:
            raise ImportError("Package cma is not installed!")

        types, bounds = get_types(self.config_space)
        assert all(types == 0)

        # Check Constant Hyperparameter
        const_idx = list()
        for i, bound in enumerate(bounds):
            if np.isnan(bound[1]):
                const_idx.append(i)

        hp_num = len(bounds) - len(const_idx)
        es = CMAEvolutionStrategy(hp_num * [0], 0.99, inopts={'bounds': [0, 1]})

        eval_num = 0
        next_configs_by_acq_value = list()
        while eval_num < num_points:
            X = es.ask(number=es.popsize)
            _X = X.copy()
            for i in range(len(_X)):
                for index in const_idx:
                    _X[i] = np.insert(_X[i], index, 0)
            _X = np.asarray(_X)
            values = self.acquisition_function._compute(_X)
            values = np.reshape(values, (-1,))
            es.tell(X, values)
            next_configs_by_acq_value.extend([(values[i], _X[i]) for i in range(es.popsize)])
            eval_num += es.popsize

        next_configs_by_acq_value.sort(reverse=True, key=lambda x: x[0])
        next_configs_by_acq_value = [_[1] for _ in next_configs_by_acq_value]
        next_configs_by_acq_value = [Configuration(self.config_space, vector=array) for array in
                                     next_configs_by_acq_value]

        challengers = ChallengerList(next_configs_by_acq_value,
                                     self.config_space,
                                     self.random_chooser)
        self.random_chooser.next_smbo_iteration()
        return challengers


class LocalSearch(AcquisitionFunctionMaximizer):
    """Implementation of openbox's local search.

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    rng : np.random.RandomState or int, optional

    max_steps: int
        Maximum number of iterations that the local search will perform

    n_steps_plateau_walk: int
        number of steps during a plateau walk before local search terminates

    """

    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rng: Union[bool, np.random.RandomState] = None,
            max_steps: Optional[int] = None,
            n_steps_plateau_walk: int = 10,
    ):
        super().__init__(acquisition_function, config_space, rng)
        # Hard cap for local search steps per start (fallback if None)
        # Reduced from 300 to 50 for faster convergence with large config spaces
        self.max_steps = max_steps if max_steps is not None else 50
        self.n_steps_plateau_walk = n_steps_plateau_walk
        # Early-stop for tiny gains
        self.improvement_tolerance = 1e-6  # stop counting gains below this
        # Reduced from 50 to 15 for faster termination
        self.small_gain_patience = 15      # end search after this many tiny gains
        # Per-iteration neighbor cap to bound work
        # Reduced from 1000 to 150 for faster neighbor evaluation
        self.neighbor_cap = 150


    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> List[Tuple[float, Configuration]]:
        """Starts a local search from the given startpoint and quits
        if either the max number of steps is reached or no neighbor
        with an higher improvement was found.

        Parameters
        ----------
        runhistory: ~autotune.utils.history_container.HistoryContainer
            runhistory object
        stats: ~autotune.stats.stats.Stats
            current stats object
        num_points: int
            number of points to be sampled
        ***kwargs:
            Additional parameters that will be passed to the
            acquisition function

        Returns
        -------
        incumbent: np.array(1, D)
            The best found configuration
        acq_val_incumbent: np.array(1,1)
            The acquisition value of the incumbent

        """

        acq_opt_start_time = time.time()
        
        init_points = self._get_initial_points(
            num_points, runhistory)

        # Debug logging for acquisition optimization
        self.logger.info(
            f"[AcqOpt] Starting acquisition optimization: {len(init_points)} local searches, "
            f"max_steps={self.max_steps}, neighbor_cap={self.neighbor_cap}"
        )
        if hasattr(runhistory, 'synthetic_flags'):
            total_configs = len(runhistory.configurations)
            # Treat missing tail as real if flags are shorter than configurations
            flags = list(runhistory.synthetic_flags)
            if len(flags) < total_configs:
                flags = flags + [False] * (total_configs - len(flags))
            synthetic_count = sum(1 for f in flags if f)
            real_count = total_configs - synthetic_count
            self.logger.info(f"[AcqOpt] History contains {total_configs} configs: {real_count} real, {synthetic_count} synthetic")
            self.logger.info(f"[AcqOpt] get_all_configs() returned {len(runhistory.get_all_configs())} configs (should be {real_count} real only)")

            # Extra diagnostics: real evaluations breakdown
            try:
                from autotune.utils.constants import SUCCESS  # local import to avoid cycles
                real_indices = [i for i in range(total_configs) if not flags[i]]
                data_keys = set(runhistory.data.keys()) if hasattr(runhistory, 'data') else set()

                total_real = len(real_indices)
                failed_real = 0
                duplicate_real = 0
                successful_real = 0
                excluded_samples = []  # (idx, reason)

                for i in real_indices:
                    cfg = runhistory.configurations[i]
                    state = runhistory.trial_states[i] if i < len(runhistory.trial_states) else None
                    if state != SUCCESS:
                        failed_real += 1
                        if len(excluded_samples) < 10:
                            excluded_samples.append((i, 'failed'))
                    else:
                        # SUCCESS but may be duplicate (not added to data)
                        if cfg in data_keys:
                            successful_real += 1
                        else:
                            duplicate_real += 1
                            if len(excluded_samples) < 10:
                                excluded_samples.append((i, 'duplicate'))

                data_size = len(runhistory.data) if hasattr(runhistory, 'data') else 0
                self.logger.info(
                    f"[AcqOpt] Real evals: total={total_real}, successful={successful_real}, "
                    f"failed={failed_real}, duplicates={duplicate_real}, data_size={data_size}")
                if excluded_samples:
                    self.logger.info(
                        "[AcqOpt] Excluded real configs (index -> reason): " +
                        ", ".join([f"{idx}->{reason}" for idx, reason in excluded_samples])
                    )
            except Exception as e:
                self.logger.warning(f"[AcqOpt] Diagnostics failed: {e}")

        acq_configs = []
        # Start N local search from different random start points
        for idx, start_point in enumerate(init_points):
            search_start = time.time()
            self.logger.info(f"[AcqOpt] Starting local search {idx+1}/{len(init_points)}")
            
            # Log initial acquisition value for this starting point
            init_acq_val = self.acquisition_function([start_point], **kwargs)
            init_acq_scalar = float(init_acq_val) if hasattr(init_acq_val, '__iter__') else init_acq_val
            self.logger.debug(f"[AcqOpt] Init point {idx}: acq_val={init_acq_scalar:.6f}")
            
            acq_val, configuration = self._one_iter(
                start_point, **kwargs)

            search_time = time.time() - search_start
            self.logger.info(f"[AcqOpt] Completed local search {idx+1}/{len(init_points)} in {search_time:.2f}s")

            configuration.origin = "Local Search"
            acq_configs.append((acq_val, configuration))

        # shuffle for random tie-break
        self.rng.shuffle(acq_configs)

        # sort according to acq value
        acq_configs.sort(reverse=True, key=lambda x: x[0])
        
        total_acq_opt_time = time.time() - acq_opt_start_time
        self.logger.info(
            f"[AcqOpt] Acquisition optimization completed in {total_acq_opt_time:.2f}s "
            f"({total_acq_opt_time/len(init_points):.2f}s per search)"
        )

        return acq_configs

    def _get_initial_points(self, num_points, runhistory):

        if runhistory.empty():
            init_points = self.config_space.sample_configuration(
                size=num_points)
        else:
            # initiate local search with best configurations from previous runs
            configs_previous_runs = runhistory.get_all_configs()
            configs_previous_runs = configs2space(configs_previous_runs, self.config_space)

            configs_previous_runs_sorted = self._sort_configs_by_acq_value(
                configs_previous_runs)
            num_configs_local_search = int(min(
                len(configs_previous_runs_sorted),
                num_points)
            )
            init_points = list(
                map(lambda x: x[1],
                    configs_previous_runs_sorted[:num_configs_local_search])
            )

        return init_points

    def _one_iter(
            self,
            start_point: Configuration,
            **kwargs
    ) -> Tuple[float, Configuration]:
        
        start_time_total = time.time()
        
        incumbent = start_point
        # Compute the acquisition value of the incumbent
        acq_start = time.time()
        acq_val_incumbent = self.acquisition_function([incumbent], **kwargs)[0]
        acq_time_initial = time.time() - acq_start
        
        self.logger.info(
            f"[AcqOpt] Starting local search from init_acq={float(acq_val_incumbent):.6f} "
            f"(eval took {acq_time_initial:.3f}s)"
        )

        local_search_steps = 0
        neighbors_looked_at = 0
        time_n = []
        time_neighbor_gen = []
        improvements = 0  # Track number of improvements found
        plateau_steps = 0  # Track steps without improvement
        small_gain_steps = 0  # Track consecutive tiny gains
        
        while True:

            local_search_steps += 1
            step_start_time = time.time()
            
            # Log progress every 5 iterations for detailed tracking
            if local_search_steps % 5 == 0:
                acq_val_scalar = float(acq_val_incumbent) if hasattr(acq_val_incumbent, '__iter__') else acq_val_incumbent
                avg_acq_time = np.mean(time_n) if time_n else 0
                avg_neighbor_time = np.mean(time_neighbor_gen) if time_neighbor_gen else 0
                elapsed = time.time() - start_time_total
                self.logger.info(
                    f"[AcqOpt] Step {local_search_steps}/{self.max_steps}: "
                    f"acq={acq_val_scalar:.6f}, impr={improvements}, plateau={plateau_steps}, "
                    f"neighbors={neighbors_looked_at}, avg_acq={avg_acq_time:.3f}s, "
                    f"avg_neighgen={avg_neighbor_time:.3f}s, elapsed={elapsed:.1f}s"
                )
            
            if local_search_steps % 20 == 0:
                acq_val_scalar = float(acq_val_incumbent) if hasattr(acq_val_incumbent, '__iter__') else acq_val_incumbent
                elapsed = time.time() - start_time_total
                self.logger.warning(
                    f"[AcqOpt] Local search took already {local_search_steps} iterations "
                    f"({elapsed:.1f}s elapsed). Possible stuck?"
                )
                self.logger.warning(
                    f"[AcqOpt] Details: acq_val={acq_val_scalar:.6f}, "
                    f"improvements={improvements}, neighbors_checked={neighbors_looked_at}, "
                    f"plateau_steps={plateau_steps}, small_gain_steps={small_gain_steps}"
                )

            # Get neighborhood of the current incumbent
            # by randomly drawing configurations
            changed_inc = False

            # Get one exchange neighborhood returns an iterator. Cap how many we consider.
            neighbor_gen_start = time.time()
            all_neighbors_iter = get_one_exchange_neighbourhood(incumbent, seed=42)
            # Limit neighbors per iteration to reduce work
            limited_neighbors = itertools.islice(all_neighbors_iter, self.neighbor_cap)
            neighbor_gen_time = time.time() - neighbor_gen_start
            time_neighbor_gen.append(neighbor_gen_time)

            neighbors_this_iter = 0
            for neighbor in limited_neighbors:
                s_time = time.time()
                acq_val = self.acquisition_function([neighbor], **kwargs)
                neighbors_looked_at += 1
                neighbors_this_iter += 1
                acq_eval_time = time.time() - s_time
                time_n.append(acq_eval_time)
                
                # Log slow acquisition evaluations
                if acq_eval_time > 2.0:
                    self.logger.warning(
                        f"[AcqOpt] Slow acquisition eval: {acq_eval_time:.2f}s "
                        f"(step {local_search_steps}, neighbor {neighbors_this_iter}/{self.neighbor_cap})"
                    )

                if acq_val > acq_val_incumbent:
                    self.logger.debug("Switch to one of the neighbors")
                    # Check improvement magnitude before updating
                    try:
                        delta = float(acq_val) - float(acq_val_incumbent)
                    except Exception:
                        delta = 0.0
                    incumbent = neighbor
                    acq_val_incumbent = acq_val
                    improvements += 1
                    plateau_steps = 0  # Reset plateau counter
                    if delta < self.improvement_tolerance:
                        small_gain_steps += 1
                    else:
                        small_gain_steps = 0
                    changed_inc = True
                    break

            # Track plateau (no improvement found this iteration)
            if not changed_inc:
                plateau_steps += 1

            # Early stop if too many tiny gains
            if small_gain_steps >= self.small_gain_patience:
                self.logger.info(
                    f"[AcqOpt] Early stop due to tiny gains: tolerance={self.improvement_tolerance}, "
                    f"patience={self.small_gain_patience}, small_gain_steps={small_gain_steps}"
                )
                self.logger.info(
                    f"[AcqOpt] Local search interim: steps={local_search_steps}, improvements={improvements}"
                )
                break

            # Stop if no change (plateau) or step cap reached
            if (not changed_inc) or (local_search_steps >= self.max_steps):
                total_time = time.time() - start_time_total
                avg_acq_time = np.mean(time_n) if time_n else 0
                avg_neighbor_time = np.mean(time_neighbor_gen) if time_neighbor_gen else 0
                total_acq_time = sum(time_n) if time_n else 0
                total_neighbor_time = sum(time_neighbor_gen) if time_neighbor_gen else 0
                
                self.logger.debug("Local search took %d steps and looked at %d "
                                  "configurations. Computing the acquisition "
                                  "value for one configuration took %f seconds"
                                  " on average.",
                                  local_search_steps, neighbors_looked_at,
                                  avg_acq_time)
                acq_val_scalar = float(acq_val_incumbent) if hasattr(acq_val_incumbent, '__iter__') else acq_val_incumbent
                self.logger.info(
                    f"[AcqOpt] Local search completed: steps={local_search_steps}, "
                    f"improvements={improvements}, final_acq={acq_val_scalar:.6f}"
                )
                self.logger.info(
                    f"[AcqOpt] Time breakdown: total={total_time:.2f}s, "
                    f"acq_eval={total_acq_time:.2f}s ({total_acq_time/total_time*100:.1f}%), "
                    f"neighbor_gen={total_neighbor_time:.2f}s ({total_neighbor_time/total_time*100:.1f}%), "
                    f"avg_per_acq={avg_acq_time:.3f}s, avg_per_neighgen={avg_neighbor_time:.3f}s"
                )
                break

        return acq_val_incumbent, incumbent


class RandomSearch(AcquisitionFunctionMaximizer):
    """Get candidate solutions via random sampling of configurations.

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    rng : np.random.RandomState or int, optional
    """

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            _sorted: bool = False,
            **kwargs
    ) -> List[Tuple[float, Configuration]]:
        """Randomly sampled configurations

        Parameters
        ----------
        runhistory: ~autotune.utils.history_container.HistoryContainer
            runhistory object
        num_points: int
            number of points to be sampled
        _sorted: bool
            whether random configurations are sorted according to acquisition function
        **kwargs
            not used

        Returns
        -------
        iterable
            An iterable consistng of
            tuple(acqusition_value, :class:`autotune.config_space.Configuration`).
        """

        if num_points > 1:
            rand_configs = self.config_space.sample_configuration(
                size=num_points)
        else:
            rand_configs = [self.config_space.sample_configuration(size=1)]
        if _sorted:
            for i in range(len(rand_configs)):
                rand_configs[i].origin = 'Random Search (sorted)'
            return self._sort_configs_by_acq_value(rand_configs)
        else:
            for i in range(len(rand_configs)):
                rand_configs[i].origin = 'Random Search'
            return [(0, rand_configs[i]) for i in range(len(rand_configs))]


class InterleavedLocalAndRandomSearch(AcquisitionFunctionMaximizer):
    """Implements openbox's default acquisition function optimization.

    This acq_maximizer performs local search from the previous best points
    according, to the acquisition function, uses the acquisition function to
    sort randomly sampled configurations and interleaves unsorted, randomly
    sampled configurations in between.

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    rng : np.random.RandomState or int, optional

    max_steps: int
        [LocalSearch] Maximum number of steps that the local search will perform

    n_steps_plateau_walk: int
        [LocalSearch] number of steps during a plateau walk before local search terminates

    n_sls_iterations: int
        [Local Search] number of local search iterations

    """

    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rng: Union[bool, np.random.RandomState] = None,
            max_steps: Optional[int] = None,
            n_steps_plateau_walk: int = 10,
            n_sls_iterations: int = 10,
            rand_prob=0.25
    ):
        super().__init__(acquisition_function, config_space, rng)
        self.random_search = RandomSearch(
            acquisition_function=acquisition_function,
            config_space=config_space,
            rng=rng
        )
        self.local_search = LocalSearch(
            acquisition_function=acquisition_function,
            config_space=config_space,
            rng=rng,
            max_steps=max_steps,
            n_steps_plateau_walk=n_steps_plateau_walk
        )
        self.n_sls_iterations = n_sls_iterations
        self.random_chooser = ChooserProb(prob=rand_prob, rng=rng)

        # =======================================================================
        # self.local_search = DiffOpt(
        #     acquisition_function=acquisition_function,
        #     config_space=config_space,
        #     rng=rng
        # )
        # =======================================================================

    def maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            random_configuration_chooser=None,
            **kwargs
    ) -> Iterable[Configuration]:
        """Maximize acquisition function using ``_maximize``.

        Parameters
        ----------
        runhistory: ~autotune.utils.history_container.HistoryContainer
            runhistory object
        num_points: int
            number of points to be sampled
        random_configuration_chooser: ~autotune.optimizer.acq_maximizer.random_configuration_chooser.RandomConfigurationChooser
            part of the returned ChallengerList such
            that we can interleave random configurations
            by a scheme defined by the random_configuration_chooser;
            random_configuration_chooser.next_smbo_iteration()
            is called at the end of this function
        **kwargs
            passed to acquisition function

        Returns
        -------
        Iterable[Configuration]
            to be concrete: ~autotune.ei_optimization.ChallengerList
        """
        next_configs_by_local_search = self.local_search._maximize(
            runhistory, self.n_sls_iterations, **kwargs
        )

        # Get configurations sorted by EI
        next_configs_by_random_search_sorted = self.random_search._maximize(
            runhistory,
            num_points - len(next_configs_by_local_search),
            _sorted=True,
        )

        # Having the configurations from random search, sorted by their
        # acquisition function value is important for the first few iterations
        # of autotune. As long as the random forest predicts constant value, we
        # want to use only random configurations. Having them at the begging of
        # the list ensures this (even after adding the configurations by local
        # search, and then sorting them)
        next_configs_by_acq_value = (
                next_configs_by_random_search_sorted
                + next_configs_by_local_search
        )
        next_configs_by_acq_value.sort(reverse=True, key=lambda x: x[0])
        self.logger.debug(
            "First 10 acq func (origin) values of selected configurations: %s",
            str([[_[0], _[1].origin] for _ in next_configs_by_acq_value[:10]])
        )
        next_configs_by_acq_value = [_[1] for _ in next_configs_by_acq_value]

        challengers = ChallengerList(next_configs_by_acq_value,
                                     self.config_space,
                                     self.random_chooser)
        self.random_chooser.next_smbo_iteration()
        return challengers

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        raise NotImplementedError()

    def set_compact_space(self, space):
        self.config_space = space
        self.random_search.set_compact_space(space)
        self.local_search.set_compact_space(space)



class ScipyOptimizer(AcquisitionFunctionMaximizer):
    """
    Wraps scipy optimizer. Only on continuous dims.

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    rng : np.random.RandomState or int, optional
    """

    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rand_prob: float = 0.0,
            rng: Union[bool, np.random.RandomState] = None,
    ):
        super().__init__(acquisition_function, config_space, rng)
        self.random_chooser = ChooserProb(prob=rand_prob, rng=rng)

        types, bounds = get_types(self.config_space)    # todo: support constant hp in scipy optimizer
        assert all(types == 0), 'Scipy optimizer (L-BFGS-B) only supports Integer and Float parameters.'
        self.bounds = bounds

        options = dict(disp=False, maxiter=1000)
        self.scipy_config = dict(tol=None, method='L-BFGS-B', options=options)

    def maximize(
            self,
            runhistory: HistoryContainer,
            initial_config=None,
            **kwargs
    ) -> List[Tuple[float, Configuration]]:

        def negative_acquisition(x):
            # shape of x = (d,)
            x = np.clip(x, 0.0, 1.0)    # fix numerical problem in L-BFGS-B
            return -self.acquisition_function(x, convert=False)[0]  # shape=(1,)

        if initial_config is None:
            initial_config = self.config_space.sample_configuration()
        init_point = initial_config.get_array()

        acq_configs = []
        result = scipy.optimize.minimize(fun=negative_acquisition,
                                         x0=init_point,
                                         bounds=self.bounds,
                                         **self.scipy_config)
        # if result.success:
        #     acq_configs.append((result.fun, Configuration(self.config_space, vector=result.x)))
        if not result.success:
            self.logger.debug('Scipy optimizer failed. Info:\n%s' % (result,))
        try:
            x = np.clip(result.x, 0.0, 1.0)  # fix numerical problem in L-BFGS-B
            config = Configuration(self.config_space, vector=x)
            acq = self.acquisition_function(x, convert=False)
            acq_configs.append((acq, config))
        except Exception:
            pass

        if not acq_configs:  # empty
            self.logger.warning('Scipy optimizer failed. Return empty config list. Info:\n%s' % (result,))

        challengers = ChallengerList([config for _, config in acq_configs],
                                     self.config_space,
                                     self.random_chooser)
        self.random_chooser.next_smbo_iteration()
        return challengers

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        raise NotImplementedError()


class RandomScipyOptimizer(AcquisitionFunctionMaximizer):
    """
    Use scipy.optimize with start points chosen by random search. Only on continuous dims.

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    rng : np.random.RandomState or int, optional
    """

    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rand_prob: float = 0.0,
            rng: Union[bool, np.random.RandomState] = None,
    ):
        super().__init__(acquisition_function, config_space, rng)

        self.random_chooser = ChooserProb(prob=rand_prob, rng=rng)

        self.random_search = InterleavedLocalAndRandomSearch(
            acquisition_function=acquisition_function,
            config_space=config_space,
            rng=rng
        )
        self.scipy_optimizer = ScipyOptimizer(
            acquisition_function=acquisition_function,
            config_space=config_space,
            rng=rng
        )

    def maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            num_trials=10,
            **kwargs
    ) -> List[Tuple[float, Configuration]]:
        assert num_trials >= 3
        acq_configs = []

        initial_configs = self.random_search.maximize(runhistory, num_points, **kwargs).challengers
        initial_acqs = self.acquisition_function(initial_configs)
        acq_configs.extend(zip(initial_acqs, initial_configs))

        scipy_initial_configs = [initial_configs[0]] + self.config_space.sample_configuration(num_trials - 1)
        success_count = 0
        for config in scipy_initial_configs:
            scipy_configs = self.scipy_optimizer.maximize(runhistory, initial_config=config).challengers
            if not scipy_configs:   # empty
                continue
            scipy_acqs = self.acquisition_function(scipy_configs)
            acq_configs.extend(zip(scipy_acqs, scipy_configs))
            success_count += 1
        if success_count == 0:
            self.logger.warning('None of Scipy optimizations are successful in RandomScipyOptimizer.')

        # shuffle for random tie-break
        self.rng.shuffle(acq_configs)

        # sort according to acq value
        acq_configs.sort(reverse=True, key=lambda x: x[0])

        configs = [_[1] for _ in acq_configs]

        challengers = ChallengerList(configs,
                                     self.config_space,
                                     self.random_chooser)
        self.random_chooser.next_smbo_iteration()
        return challengers

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        raise NotImplementedError()


class ScipyGlobalOptimizer(AcquisitionFunctionMaximizer):
    """
    Wraps scipy global optimizer. Only on continuous dims.

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    rng : np.random.RandomState or int, optional
    """

    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rand_prob: float = 0.0,
            rng: Union[bool, np.random.RandomState] = None,
    ):
        super().__init__(acquisition_function, config_space, rng)
        self.random_chooser = ChooserProb(prob=rand_prob, rng=rng)

        types, bounds = get_types(self.config_space)
        assert all(types == 0)
        self.bounds = bounds

    def maximize(
            self,
            runhistory: HistoryContainer,
            initial_config=None,
            **kwargs
    ) -> List[Tuple[float, Configuration]]:

        def negative_acquisition(x):
            # shape of x = (d,)
            return -self.acquisition_function(x, convert=False)[0]  # shape=(1,)

        acq_configs = []
        result = scipy.optimize.differential_evolution(func=negative_acquisition,
                                                       bounds=self.bounds)
        if not result.success:
            self.logger.debug('Scipy differential evolution optimizer failed. Info:\n%s' % (result,))
        try:
            config = Configuration(self.config_space, vector=result.x)
            acq = self.acquisition_function(result.x, convert=False)
            acq_configs.append((acq, config))
        except Exception:
            pass

        if not acq_configs:  # empty
            self.logger.warning('Scipy differential evolution optimizer failed. Return empty config list. Info:\n%s' % (result,))

        challengers = ChallengerList([config for _, config in acq_configs],
                                     self.config_space,
                                     self.random_chooser)
        self.random_chooser.next_smbo_iteration()
        return challengers

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        raise NotImplementedError()


class StagedBatchScipyOptimizer(AcquisitionFunctionMaximizer):
    """ todo constraints
    Use batch scipy.optimize with start points chosen by specific method. Only on continuous dims.

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    num_random : Number of random chosen points

    num_restarts : The number of starting points for multistart acquisition
            function optimization

    raw_samples : The number of samples for initialization

    batch_limit : Number of points in a batch optimized jointly by scipy minimizer

    scipy_maxiter : Maximum number of scipy minimizer iterations to perform

    rand_prob : Probability of choosing random config

    rng : np.random.RandomState or int, optional
    """

    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            num_random: int = 1000,
            num_restarts: int = 20,
            raw_samples: int = 1024,
            batch_limit: int = 5,
            scipy_maxiter: int = 200,
            rand_prob: float = 0.0,
            rng: Union[bool, np.random.RandomState] = None,
    ):
        super().__init__(acquisition_function, config_space, rng)
        self.num_random = num_random
        self.num_restarts = num_restarts
        self.raw_samples = raw_samples
        self.batch_limit = batch_limit
        self.scipy_max_iter = scipy_maxiter
        self.random_chooser = ChooserProb(prob=rand_prob, rng=rng)
        self.minimizer = scipy.optimize.minimize
        self.method = "L-BFGS-B"
        self.dim = len(self.config_space.get_hyperparameters())
        self.bound = (0.0, 1.0)  # todo only on continuous dims (int, float) now

    def gen_initial_points(self, num_restarts, raw_samples):
        # todo other strategy
        random_points = self.rng.uniform(self.bound[0], self.bound[1], size=(raw_samples, self.dim))
        acq_random = self.acquisition_function(random_points, convert=False).reshape(-1)
        idx = np.argsort(acq_random)[::-1][:num_restarts]
        return random_points[idx]

    def gen_batch_scipy_points(self, initial_points: np.ndarray):
        #count = 0  # todo remove
        def f(X_flattened):
            # nonlocal count
            # count += 1
            X = X_flattened.reshape(shapeX)
            joint_acq = -self.acquisition_function(X, convert=False).sum().item()
            return joint_acq

        shapeX = initial_points.shape
        x0 = initial_points.reshape(-1)
        bounds = [self.bound] * x0.shape[0]

        result = self.minimizer(
            f,
            x0=x0,
            method=self.method,
            bounds=bounds,
            options=dict(maxiter=self.scipy_max_iter),
        )
        #print('count=', count)  # todo remove

        # return result.x even failed. may because 'STOP: TOTAL NO. of ITERATIONS REACHED LIMIT'
        # if not result.success:
        #     self.logger.warning('Scipy minimizer %s failed in this round: %s.' % (self.method, result))
        #     return None

        #print(result.x.reshape(shapeX))    # todo remove
        return result.x.reshape(shapeX)

    def maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,  # todo useless
            **kwargs
    ) -> List[Tuple[float, Configuration]]:

        # print('start optimize')   # todo remove
        # import time
        # t0 = time.time()
        acq_configs = []

        # random points
        random_points = self.rng.uniform(self.bound[0], self.bound[1], size=(self.num_random, self.dim))
        acq_random = self.acquisition_function(random_points, convert=False)
        for i in range(random_points.shape[0]):
            # convert array to Configuration
            config = Configuration(self.config_space, vector=random_points[i])
            config.origin = 'Random Search'
            acq_configs.append((acq_random[i], config))

        # scipy points
        initial_points = self.gen_initial_points(num_restarts=self.num_restarts, raw_samples=self.raw_samples)

        for start_idx in range(0, self.num_restarts, self.batch_limit):
            end_idx = min(start_idx + self.batch_limit, self.num_restarts)
            # optimize using random restart optimization
            scipy_points = self.gen_batch_scipy_points(initial_points[start_idx:end_idx])
            if scipy_points is None:
                continue
            acq_scipy = self.acquisition_function(scipy_points, convert=False)
            for i in range(scipy_points.shape[0]):
                # convert array to Configuration
                config = Configuration(self.config_space, vector=scipy_points[i])
                config.origin = 'Batch Scipy'
                acq_configs.append((acq_scipy[i], config))

        # shuffle for random tie-break
        self.rng.shuffle(acq_configs)

        # sort according to acq value
        acq_configs.sort(reverse=True, key=lambda x: x[0])

        configs = [_[1] for _ in acq_configs]

        challengers = ChallengerList(configs,
                                     self.config_space,
                                     self.random_chooser)
        self.random_chooser.next_smbo_iteration()

        # t1 = time.time()  # todo remove
        # print('==time total=%.2f' % (t1-t0,))
        # for x1 in np.linspace(0, 1, 20):
        #     optimal_point = np.array([x1.item()] + [0.5] * (self.dim-1))
        #     print('optimal_point acq=', self.acquisition_function(optimal_point, convert=False))
        # print('best point acq=', acq_configs[0])
        # time.sleep(2)
        return challengers

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        raise NotImplementedError()


class MESMO_Optimizer(AcquisitionFunctionMaximizer):
    """Implements Scipy optimizer for MESMO. Only on continuous dims

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    rng : np.random.RandomState or int, optional

    """

    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rng: Union[bool, np.random.RandomState] = None,
            num_mc=1000,
            num_opt=1000,
            rand_prob=0.0,
    ):
        super().__init__(acquisition_function, config_space, rng)
        self.random_chooser = ChooserProb(prob=rand_prob, rng=rng)
        self.num_mc = num_mc
        self.num_opt = num_opt
        self.minimizer = scipy.optimize.minimize

    def maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,  # todo useless
            **kwargs
    ) -> Iterable[Configuration]:
        """Maximize acquisition function using ``_maximize``.

        Parameters
        ----------
        runhistory: ~autotune.utils.history_container.HistoryContainer
            runhistory object
        num_points: int
            number of points to be sampled
        **kwargs
            passed to acquisition function

        Returns
        -------
        Iterable[Configuration]
            to be concrete: ~autotune.ei_optimization.ChallengerList
        """

        def inverse_acquisition(x):
            # shape of x = (d,)
            return -self.acquisition_function(x, convert=False)[0]  # shape=(1,)

        d = len(self.config_space.get_hyperparameters())
        bound = (0.0, 1.0)  # todo only on continuous dims (int, float) now
        bounds = [bound] * d
        acq_configs = []

        # MC
        x_tries = self.rng.uniform(bound[0], bound[1], size=(self.num_mc, d))
        acq_tries = self.acquisition_function(x_tries, convert=False)
        for i in range(x_tries.shape[0]):
            # convert array to Configuration
            config = Configuration(self.config_space, vector=x_tries[i])
            config.origin = 'Random Search'
            acq_configs.append((acq_tries[i], config))

        # L-BFGS-B
        x_seed = self.rng.uniform(low=bound[0], high=bound[1], size=(self.num_opt, d))
        for i in range(x_seed.shape[0]):
            x0 = x_seed[i].reshape(1, -1)
            result = self.minimizer(inverse_acquisition, x0=x0, method='L-BFGS-B', bounds=bounds)
            if not result.success:
                continue
            # convert array to Configuration
            config = Configuration(self.config_space, vector=result.x)
            config.origin = 'Scipy'
            acq_val = self.acquisition_function(result.x, convert=False)  # [0]
            acq_configs.append((acq_val, config))

        # shuffle for random tie-break
        self.rng.shuffle(acq_configs)

        # sort according to acq value
        acq_configs.sort(reverse=True, key=lambda x: x[0])

        configs = [_[1] for _ in acq_configs]

        challengers = ChallengerList(configs,
                                     self.config_space,
                                     self.random_chooser)
        self.random_chooser.next_smbo_iteration()
        return challengers

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        raise NotImplementedError()


class USeMO_Optimizer(AcquisitionFunctionMaximizer):
    """Implements USeMO optimizer

    Parameters
    ----------
    acquisition_function : ~autotune.optimizer.acquisition_function.acquisition.AbstractAcquisitionFunction

    config_space : ~autotune.config_space.ConfigurationSpace

    rng : np.random.RandomState or int, optional

    """

    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rng: Union[bool, np.random.RandomState] = None,
            rand_prob=0.0,
    ):
        super().__init__(acquisition_function, config_space, rng)
        self.random_chooser = ChooserProb(prob=rand_prob, rng=rng)

    def maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,  # useless in USeMO
            **kwargs
    ) -> Iterable[Configuration]:
        """Maximize acquisition function using ``_maximize``.

        Parameters
        ----------
        runhistory: ~autotune.utils.history_container.HistoryContainer
            runhistory object
        num_points: int
            number of points to be sampled
        **kwargs
            passed to acquisition function

        Returns
        -------
        Iterable[Configuration]
            to be concrete: ~autotune.ei_optimization.ChallengerList
        """

        acq_vals = np.asarray(self.acquisition_function.uncertainties)
        candidates = np.asarray(self.acquisition_function.candidates)
        assert len(acq_vals.shape) == 1 and len(candidates.shape) == 2 \
               and acq_vals.shape[0] == candidates.shape[0]

        acq_configs = []
        for i in range(acq_vals.shape[0]):
            # convert array to Configuration todo
            config = Configuration(self.config_space, vector=candidates[i])
            acq_configs.append((acq_vals[i], config))

        # shuffle for random tie-break
        self.rng.shuffle(acq_configs)

        # sort according to acq value
        acq_configs.sort(reverse=True, key=lambda x: x[0])

        configs = [_[1] for _ in acq_configs]

        challengers = ChallengerList(configs,
                                     self.config_space,
                                     self.random_chooser)
        self.random_chooser.next_smbo_iteration()
        return challengers

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        raise NotImplementedError()


class batchMCOptimizer(AcquisitionFunctionMaximizer):
    def __init__(
            self,
            acquisition_function: AbstractAcquisitionFunction,
            config_space: ConfigurationSpace,
            rng: Union[bool, np.random.RandomState] = None,
            batch_size=None,
            rand_prob=0.0,
    ):
        super().__init__(acquisition_function, config_space, rng)
        self.random_chooser = ChooserProb(prob=rand_prob, rng=rng)

        if batch_size is None:
            types, bounds = get_types(self.config_space)
            dim = np.sum(types == 0)
            self.batch_size = min(5000, max(2000, 200 * dim))
        else:
            self.batch_size = batch_size

    def maximize(
            self,
            runhistory: Union[HistoryContainer, MultiStartHistoryContainer],
            num_points: int,
            _sorted: bool = True,
            **kwargs
    ) -> List[Tuple[float, Configuration]]:
        """Randomly sampled configurations

        Parameters
        ----------
        runhistory: ~autotune.utils.history_container.HistoryContainer
            runhistory object
        num_points: int
            number of points to be sampled
        _sorted: bool
            whether random configurations are sorted according to acquisition function
        **kwargs
            turbo_state: TurboState
                provide turbo state to use trust region

        Returns
        -------
        iterable
            An iterable consistng of
            tuple(acqusition_value, :class:`autotune.config_space.Configuration`).
        """
        from autotune.utils.samplers import SobolSampler

        cur_idx = 0
        config_acq = list()
        weight_seed = 42  # The same weight seed each iteration

        while cur_idx < num_points:
            batch_size = min(self.batch_size, num_points - cur_idx)
            turbo_state = kwargs.get('turbo_state', None)
            if turbo_state is None:
                lower_bounds = None
                upper_bounds = None
            else:
                assert isinstance(runhistory, MultiStartHistoryContainer)
                if runhistory.num_objs > 1:
                    # TODO implement adaptive strategy to choose trust region center for MO
                    raise NotImplementedError()
                else:
                    x_center = random.choice(runhistory.get_incumbents())[0].get_array()
                    lower_bounds = x_center - turbo_state.length / 2.0
                    upper_bounds = x_center + turbo_state.length / 2.0

            sobol_sampler = SobolSampler(self.config_space, batch_size,
                                         lower_bounds, upper_bounds,
                                         random_state=self.rng.randint(0, int(1e8)))
            _configs = sobol_sampler.generate(return_config=True)
            _acq_values = self.acquisition_function(_configs, seed=42)
            config_acq.extend([(_configs[idx], _acq_values[idx]) for idx in range(len(_configs))])

            cur_idx += self.batch_size

        config_acq.sort(reverse=True, key=lambda x: x[1])

        challengers = ChallengerList([_[0] for _ in config_acq],
                                     self.config_space,
                                     self.random_chooser)
        self.random_chooser.next_smbo_iteration()
        return challengers

    def _maximize(
            self,
            runhistory: HistoryContainer,
            num_points: int,
            **kwargs
    ) -> Iterable[Tuple[float, Configuration]]:
        raise NotImplementedError()


class ChallengerList(object):
    """Helper class to interleave random configurations in a list of challengers.

    Provides an iterator which returns a random configuration in each second
    iteration. Reduces time necessary to generate a list of new challengers
    as one does not need to sample several hundreds of random configurations
    in each iteration which are never looked at.

    Parameters
    ----------
    challengers : list
        List of challengers (without interleaved random configurations)

    configuration_space : ConfigurationSpace
        ConfigurationSpace from which to sample new random configurations.
    """

    def __init__(self, challengers, configuration_space, random_configuration_chooser=ChooserNoCoolDown(2.0)):
        self.challengers = challengers
        self.configuration_space = configuration_space
        self._index = 0
        self._iteration = 1  # 1-based to prevent from starting with a random configuration
        self.random_configuration_chooser = random_configuration_chooser

    def __iter__(self):
        return self

    def __next__(self):
        if self._index == len(self.challengers):
            raise StopIteration
        else:
            if self.random_configuration_chooser.check(self._iteration):
                config = self.configuration_space.sample_configuration()
                config.origin = 'Random Search'
            else:
                config = self.challengers[self._index]
                self._index += 1
            self._iteration += 1
            return config
