import json
import numpy as np
import matplotlib.pyplot as plt
def plot_convergence(
    x,
    y1,
    y2,
    xlabel="Number of iterations $n$",
    ylabel=r"Min objective value after $n$ iterations",
    ax=None,
    name=None,
    alpha=0.2,
    yscale=None,
    color=None,
    true_minimum=None,
    **kwargs
):
    """Plot one or several convergence traces.

    Parameters
    ----------
    args[i] :  `OptimizeResult`, list of `OptimizeResult`, or tuple
        The result(s) for which to plot the convergence trace.

        - if `OptimizeResult`, then draw the corresponding single trace;
        - if list of `OptimizeResult`, then draw the corresponding convergence
          traces in transparency, along with the average convergence trace;
        - if tuple, then `args[i][0]` should be a string label and `args[i][1]`
          an `OptimizeResult` or a list of `OptimizeResult`.

    ax : `Axes`, optional
        The matplotlib axes on which to draw the plot, or `None` to create
        a new one.

    true_minimum : float, optional
        The true minimum value of the function, if known.

    yscale : None or string, optional
        The scale for the y-axis.

    Returns
    -------
    ax : `Axes`
        The matplotlib axes.
    """
    if ax is None:
        ax = plt.gca()

    plt.title("Convergence plot")
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid()

    if yscale is not None:
        plt.yscale(yscale)

    plt.plot(x, y1, c=color, label=name, **kwargs)
    plt.scatter(x, y2, c=color, alpha=alpha)

    if true_minimum is not None:
        plt.axhline(true_minimum, linestyle="--", color="r", lw=1, label="True minimum")

    if true_minimum is not None or name is not None:
        plt.legend(loc="upper right")


for x in [
    "/root/OpAdviserPrivate/repo/history_sbread.json",
    "/root/OpAdviserPrivate/repo/history_sbread_ground_truth2.json",
]:
    with open(x) as f:
        j = json.load(f)["data"]
        perfs = list(map(lambda x: -x["external_metrics"].get("tps", 0), j))
        xlabel = "Number of iterations $n$"
        ylabel = r"Min objective value after $n$ iterations"
        ax = None
        name = None
        alpha = 0.2
        yscale = None
        color = None
        true_minimum = None
        losses = list(perfs)
        n_calls = len(losses)
        iterations = range(1, n_calls + 1)
        mins = [np.min(losses[:i]) for i in iterations]
        max_mins = max(mins)
        cliped_losses = np.clip(losses, None, max_mins)
        plot_convergence(
            iterations,
            mins,
            cliped_losses,
            xlabel,
            ylabel,
            ax,
            name,
            alpha,
            yscale,
            color,
            true_minimum,
        )
        plt.savefig('%s.png' % x)