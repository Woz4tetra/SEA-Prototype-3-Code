from data_processing.experiment_helpers.single_weight_helpers import *
from data_processing.experiment_helpers.k_calculator_helpers import compute_linear_regression


def run_single_weight_tests():
    import matplotlib.pyplot as plt
    moments = []
    errors = []
    actual_displacements = []

    weight_load_point_offset_cm = -3.2

    for net_moment, actual_displacement, error in [
        single_weight_test(18.0 - weight_load_point_offset_cm, 0.41783182292744253),
        single_weight_test(19.0 - weight_load_point_offset_cm, 0.38515925933010864),
        single_weight_test(22.0 - weight_load_point_offset_cm, 0.2984513020910304),
        single_weight_test(0.0, 0.025132741228718346, False)
    ]:
        moments.append(net_moment)
        actual_displacements.append(actual_displacement)
        errors.append(error)

    displacement_lin_reg, polynomial = compute_linear_regression(actual_displacements, moments)

    # plt.figure(1)
    # plt.plot(errors, moments, 'x')
    # plt.figure(2)
    plt.plot(actual_displacements, moments, 'x')
    plt.plot(actual_displacements, displacement_lin_reg,
             label='m=%0.4fNm/rad, b=%0.4fNm' % (polynomial[0], polynomial[1]))

    plt.legend()
    plt.show()


run_single_weight_tests()
