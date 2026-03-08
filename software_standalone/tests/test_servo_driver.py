import math

from spotmicro_standalone.config import load_config
from spotmicro_standalone.hardware import ServoDriver, create_board


def test_mock_board_receives_commands():
    cfg = load_config()
    board = create_board("mock", pwm_frequency=cfg.hardware.pwm_frequency)
    driver = ServoDriver(cfg, board)
    joint_angles = {
        name: math.radians(params.center_angle_deg)
        for name, params in cfg.servos.items()
    }

    driver.send_joint_angles(joint_angles)
    assert len(board.last_commands) == len(cfg.servos)

