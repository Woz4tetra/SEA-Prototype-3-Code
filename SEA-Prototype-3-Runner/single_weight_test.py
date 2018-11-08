import matplotlib.pyplot as plt

from data_processing.experiment_helpers.single_weight_helpers import *
from data_processing.experiment_helpers.k_calculator_helpers import compute_linear_regression
from data_processing.experiment_helpers.plot_helpers import *


def run_single_weight_tests():
    moments = []
    errors = []
    actual_displacements = []

    weight_load_point_offset_cm = 0.0
    # weight_load_point_offset_cm = -3.2
    K = 2.9887

    for net_moment, actual_displacement, error in [
        # initial_tests:
        single_weight_test(18.0 - weight_load_point_offset_cm, 0.41783182292744253, K),
        single_weight_test(19.0 - weight_load_point_offset_cm, 0.38515925933010864, K),
        single_weight_test(22.0 - weight_load_point_offset_cm, 0.2984513020910304, K),
        single_weight_test(0.0, 0.025132741228718346, K, False),

        # tipped forward:
        single_weight_test(20.0, 0.3675156696207544, K),
        single_weight_test(15.0, 0.4727224279026642, K),

        # tipped backward:
        single_weight_test(20.0, 0.35814156250923646, K),
        single_weight_test(15.0, 0.48694686130641796, K),
    ]:
        moments.append(net_moment)
        actual_displacements.append(actual_displacement)
        errors.append(error)

    displacement_lin_reg, polynomial = compute_linear_regression(actual_displacements, moments)
    actual_K = polynomial[0]

    print("More results:")
    for moment, displacement in zip(moments, actual_displacements):
        predicted_moment_with_actual_K = displacement * actual_K
        predicted_moment_with_predicted_K = displacement * K
        print("\tdisplacement:", displacement)
        print("\tactual moment: ", moment)
        print("\tpredicted moment with actual K: %s (error: %s)" % (predicted_moment_with_actual_K, moment - predicted_moment_with_actual_K))
        print("\tpredicted moment with predicted K: %s (error: %s)" % (predicted_moment_with_predicted_K, moment - predicted_moment_with_predicted_K))
        print()


    # new_fig()
    # plt.plot(errors, moments, 'x')

    new_fig()
    plt.plot(actual_displacements, moments, 'x')
    plt.plot(actual_displacements, displacement_lin_reg,
             label='m=%0.4fNm/rad, b=%0.4fNm' % (polynomial[0], polynomial[1]))

    save_fig("single_weight_test")
    plt.legend()
    plt.show()


run_single_weight_tests()
