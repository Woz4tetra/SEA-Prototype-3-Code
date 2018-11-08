import os
import matplotlib.pyplot as plt

current_fig_num = 0


def new_fig(fig_num=None):
    """Create a new figure"""

    global current_fig_num, current_fig
    if fig_num is None:
        current_fig_num += 1
    else:
        current_fig_num = fig_num
    fig = plt.figure(current_fig_num)
    fig.canvas.mpl_connect('key_press_event', press)
    current_fig = fig

    return fig


def press(event):
    """matplotlib key press event. Close all figures when q is pressed"""
    if event.key == "q":
        plt.close("all")


def mkdir(path, is_file=True):
    if is_file:
        path = os.path.split(path)[0]  # remove the file part of the path

    if not os.path.isdir(path):
        os.makedirs(path)


def save_fig(path):
    path = "figures/%s.png" % path
    mkdir(path)
    print("saving to '%s'" % path)
    plt.savefig(path, dpi=200)
