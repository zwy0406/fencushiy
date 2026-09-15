from utils import config
from utils.util_function import euclidean_distance_3d


def trajectory_based_let(traj_a, traj_b, communication_range=None):
    communication_range = communication_range or config.COMMUNICATION_RANGE
    horizon = min(len(traj_a), len(traj_b))
    let_seconds = 0.0

    for step in range(horizon):
        if euclidean_distance_3d(traj_a[step], traj_b[step]) <= communication_range:
            let_seconds += 1.0
        else:
            break

    return let_seconds


def average_tlet_for_neighbors(my_traj, neighbor_trajs, communication_range=None):
    if not neighbor_trajs:
        return 0.0
    values = [trajectory_based_let(my_traj, traj, communication_range=communication_range) for traj in neighbor_trajs]
    return sum(values) / len(values)

