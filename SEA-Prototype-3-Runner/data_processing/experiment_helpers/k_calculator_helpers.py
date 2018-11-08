import math
import peakutils
import numpy as np

default_rel_enc_ticks_to_rad = 2 * math.pi / 2000
default_motor_enc_ticks_to_rad = 2 * math.pi / (131.25 * 64)
default_abs_gear_ratio = 48.0 / 32.0


def savitzky_golay(y, window_size, order, deriv=0, rate=1):
    try:
        window_size = np.abs(np.int(window_size))
        order = np.abs(np.int(order))
    except ValueError:
        raise ValueError("window_size and order have to be of type int")

    if window_size % 2 != 1 or window_size < 1:
        raise TypeError("window_size size must be a positive odd number")

    if window_size < order + 2:
        raise TypeError("window_size is too small for the polynomials order")

    order_range = range(order + 1)
    half_window = (window_size - 1) // 2
    # precompute coefficients
    b = np.mat([[k ** i for i in order_range] for k in range(-half_window, half_window + 1)])
    m = np.linalg.pinv(b).A[deriv] * rate ** deriv * math.factorial(deriv)
    # pad the signal at the extremes with
    # values taken from the signal itself
    firstvals = y[0] - np.abs(y[1:half_window + 1][::-1] - y[0])
    lastvals = y[-1] + np.abs(y[-half_window - 1:-1][::-1] - y[-1])
    y = np.concatenate((firstvals, y, lastvals))
    return np.convolve(m[::-1], y, mode='valid')


def get_key_transistions(brake_timestamps, brake_current, motor_direction_switch_time):
    brake_ramp_transitions = peakutils.indexes(brake_current, thres=0.9, min_dist=500)
    motor_direction_switch_brake_index = (np.abs(brake_timestamps - motor_direction_switch_time)).argmin()
    assert len(brake_ramp_transitions) == 2, len(brake_ramp_transitions)
    assert motor_direction_switch_brake_index > brake_ramp_transitions[0], motor_direction_switch_brake_index

    return brake_ramp_transitions, motor_direction_switch_brake_index


def interpolate_encoder_values(encoder_timestamps, encoder_1_ticks, encoder_2_ticks, rel_enc_ticks_to_rad,
                               brake_timestamps, enable_smoothing):
    encoder_delta = (encoder_1_ticks - encoder_2_ticks) * rel_enc_ticks_to_rad
    if enable_smoothing:
        encoder_delta = savitzky_golay(encoder_delta, 501, 5)
    encoder_interp_delta = []

    interp_enc_index = 0
    for brake_t in brake_timestamps:
        # Encoder samples ~5 times faster than the brake's current feedback. Interpolate encoder values to brake timestamps
        while encoder_timestamps[interp_enc_index] < brake_t:
            interp_enc_index += 1
            if interp_enc_index >= len(encoder_timestamps):
                interp_enc_index -= 1
                break
        enc_index = interp_enc_index

        encoder_interp_delta.append(encoder_delta[enc_index])

    return encoder_interp_delta, encoder_delta


def compute_linear_regression(encoder_interp_delta, brake_torque_nm):
    polynomial = np.polyfit(encoder_interp_delta, brake_torque_nm, 1)
    linear_regression_fn = np.poly1d(polynomial)
    encoder_lin_reg = linear_regression_fn(encoder_interp_delta)
    return encoder_lin_reg, polynomial


def compute_k(torque_table,
              encoder_timestamps, encoder_1_ticks, encoder_2_ticks,
              brake_timestamps, brake_current,
              motor_direction_switch_time, enable_smoothing=False):
    rel_enc_ticks_to_rad = default_rel_enc_ticks_to_rad

    encoder_timestamps = np.array(encoder_timestamps)
    encoder_1_ticks = np.array(encoder_1_ticks)
    encoder_2_ticks = np.array(encoder_2_ticks)
    brake_timestamps = np.array(brake_timestamps)
    brake_current = np.array(brake_current)

    try:
        brake_ramp_transitions, motor_direction_switch_brake_index = get_key_transistions(brake_timestamps,
                                                                                          brake_current,
                                                                                          motor_direction_switch_time)
    except AssertionError as error:
        brake_ramp_transitions = None
        motor_direction_switch_brake_index = None
        print(error)

    encoder_interp_delta, encoder_delta = interpolate_encoder_values(encoder_timestamps, encoder_1_ticks,
                                                                     encoder_2_ticks, rel_enc_ticks_to_rad,
                                                                     brake_timestamps, enable_smoothing)

    if brake_ramp_transitions is not None:
        # convert sensed current to torque (Nm)
        brake_current_forcing_forward = brake_current[0:brake_ramp_transitions[0]]
        brake_current_unforcing_forward = brake_current[brake_ramp_transitions[0]:motor_direction_switch_brake_index]
        brake_current_forcing_backward = brake_current[motor_direction_switch_brake_index:brake_ramp_transitions[1]]
        brake_current_unforcing_backward = brake_current[brake_ramp_transitions[1]:]

        btff = torque_table.to_torque(True, brake_current_forcing_forward)
        btuf = torque_table.to_torque(False, brake_current_unforcing_forward)
        btfb = -torque_table.to_torque(True, brake_current_forcing_backward)
        btub = -torque_table.to_torque(False, brake_current_unforcing_backward)
        brake_torque_nm = np.concatenate((btff, btuf, btfb, btub))

        encoder_lin_reg, polynomial = compute_linear_regression(encoder_interp_delta, brake_torque_nm)
    else:
        brake_torque_nm = None
        encoder_lin_reg = None
        polynomial = None

    return (encoder_timestamps, encoder_delta, encoder_interp_delta, encoder_lin_reg,
            brake_timestamps, brake_current, brake_ramp_transitions, brake_torque_nm, polynomial)
