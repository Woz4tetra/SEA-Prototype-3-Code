import math
import peakutils
import numpy as np
from collections import namedtuple

ResultInfo = namedtuple(
    "ResultInfo",

    "encoder_timestamps "
    "encoder_delta "
    "encoder_interp_delta "
    "encoder_lin_reg "
    "brake_timestamps "
    "brake_current "
    "brake_ramp_transitions "
    "brake_torque_nm "
    "polynomial "
    "motor_forward_backlash_rad "
    "motor_backward_backlash_rad "
)


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


def get_brake_ramp_transitions(brake_current):
    brake_ramp_transition_indices = peakutils.indexes(brake_current, thres=0.9, min_dist=500)
    assert len(brake_ramp_transition_indices) == 2, len(brake_ramp_transition_indices)
    return brake_ramp_transition_indices


def get_motor_dir_transistion(brake_timestamps, enc_timestamps, motor_direction_switch_time):
    motor_direction_switch_brake_index = (np.abs(brake_timestamps - motor_direction_switch_time)).argmin()
    motor_direction_switch_enc_index = (np.abs(enc_timestamps - motor_direction_switch_time)).argmin()

    return motor_direction_switch_brake_index, motor_direction_switch_enc_index


def interpolate_encoder_values(encoder_timestamps, encoder_1_ticks, encoder_2_ticks, ticks_to_rad,
                               brake_timestamps, enable_smoothing):
    encoder_delta = (encoder_1_ticks - encoder_2_ticks) * ticks_to_rad
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


def get_motor_backlash(base_encoder_ticks, motor_ticks, rel_ticks_to_rad, motor_ticks_to_rad,
                       motor_direction_switch_enc_index):
    backlash_delta = base_encoder_ticks * rel_ticks_to_rad - motor_ticks * motor_ticks_to_rad

    forward = np.mean(backlash_delta[0:motor_direction_switch_enc_index])
    backward = np.mean(backlash_delta[motor_direction_switch_enc_index:])
    return forward, backward


def compute_linear_regression(encoder_interp_delta, brake_torque_nm):
    polynomial = np.polyfit(encoder_interp_delta, brake_torque_nm, 1)
    linear_regression_fn = np.poly1d(polynomial)
    encoder_lin_reg = linear_regression_fn(encoder_interp_delta)
    return encoder_lin_reg, polynomial


def format_abs_enc_ticks(abs_enc_ticks, ticks_per_rotation, fixed_diff):
    formatted_abs_ticks = []
    prev_tick = 0.0
    rotations = 0
    for tick in abs_enc_ticks:
        if 300 < tick - prev_tick < 950 or 300 < prev_tick - tick < 950:
            tick = prev_tick

        if tick - prev_tick > 950:
            rotations -= 1
        if prev_tick - tick > 950:
            rotations += 1

        total_ticks = rotations * ticks_per_rotation + tick
        total_ticks -= fixed_diff
        formatted_abs_ticks.append(total_ticks)
        prev_tick = tick

    return formatted_abs_ticks


def compute_k(torque_table,
              encoder_timestamps, encoder_1_ticks, encoder_2_ticks, motor_enc_ticks,
              brake_timestamps, brake_current,
              motor_direction_switch_time, enc_ticks_to_rad, motor_ticks_to_rad, enable_smoothing,
              start_time, stop_time):
    enc_start_index = (np.abs(encoder_timestamps - start_time)).argmin()
    enc_stop_index = (np.abs(encoder_timestamps - stop_time)).argmin()
    brake_start_index = (np.abs(brake_timestamps - start_time)).argmin()
    brake_stop_index = (np.abs(brake_timestamps - stop_time)).argmin()

    encoder_timestamps = encoder_timestamps[enc_start_index:enc_stop_index]
    encoder_1_ticks = encoder_1_ticks[enc_start_index:enc_stop_index]
    encoder_2_ticks = encoder_2_ticks[enc_start_index:enc_stop_index]
    motor_enc_ticks = motor_enc_ticks[enc_start_index:enc_stop_index]

    brake_timestamps = brake_timestamps[brake_start_index:brake_stop_index]
    brake_current = brake_current[brake_start_index:brake_stop_index]

    motor_direction_switch_brake_index, motor_direction_switch_enc_index = \
        get_motor_dir_transistion(brake_timestamps, encoder_timestamps, motor_direction_switch_time)

    try:
        brake_ramp_transition_indices = get_brake_ramp_transitions(brake_current)
    except AssertionError as error:
        brake_ramp_transition_indices = None
        motor_direction_switch_brake_index = None
        print(error)

    assert motor_direction_switch_brake_index > brake_ramp_transition_indices[0], motor_direction_switch_brake_index

    motor_forward_backlash, motor_backward_backlash = \
        get_motor_backlash(encoder_1_ticks, motor_enc_ticks, enc_ticks_to_rad, motor_ticks_to_rad,
                           motor_direction_switch_enc_index)

    encoder_interp_delta, encoder_delta = interpolate_encoder_values(
        encoder_timestamps, encoder_1_ticks, encoder_2_ticks, enc_ticks_to_rad, brake_timestamps, enable_smoothing
    )

    if brake_ramp_transition_indices is not None:
        # convert sensed current to torque (Nm)
        brake_current_forcing_forward = brake_current[0:brake_ramp_transition_indices[0]]
        brake_current_unforcing_forward = brake_current[
                                          brake_ramp_transition_indices[0]:motor_direction_switch_brake_index]
        brake_current_forcing_backward = brake_current[
                                         motor_direction_switch_brake_index:brake_ramp_transition_indices[1]]
        brake_current_unforcing_backward = brake_current[brake_ramp_transition_indices[1]:]

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

    return ResultInfo(encoder_timestamps, encoder_delta, encoder_interp_delta, encoder_lin_reg,
                      brake_timestamps, brake_current, brake_ramp_transition_indices, brake_torque_nm, polynomial,
                      motor_forward_backlash, motor_backward_backlash)
