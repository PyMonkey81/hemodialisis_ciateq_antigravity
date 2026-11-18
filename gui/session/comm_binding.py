import logging

logger = logging.getLogger(__name__)


class CommBinding:
    def __init__(self, window):
        self.window = window

    def handle_comm_config_change(self, sensor_id, port, is_enabled, simulation_enabled=False):
        if sensor_id == "MAIN_CONTROL":
            self.window.serial_comm.update_config(port, is_enabled, simulation_enabled)
            logger.info(
                "Controlador Principal: Puerto=%s, Habilitado=%s, Simulación=%s",
                port,
                is_enabled,
                simulation_enabled,
            )

        elif sensor_id == "CONDUCTIVITY":
            self.window.pattern_sensor.update_config(port, is_enabled)
            logger.info(f"Sensor Conductividad: Puerto={port}, Habilitado={is_enabled}")
        elif sensor_id == "MEGA_CONDUCTIVITY":
            self.window.mega_cond_sensor.update_config(port, is_enabled)
            logger.info(f"Sensor Conductividad MEGA: Puerto={port}, Habilitado={is_enabled}")
        elif sensor_id == "BIOZ":
            self.window.bioz_urea_controller.update_config(port, is_enabled)
            logger.info(f"Sensor BioZ: Puerto={port}, Habilitado={is_enabled}")
        elif sensor_id == "LED_CONTROLLER":
            self.window.led_bar.update_config(port, is_enabled)
            logger.info(f"LED Controller: Puerto={port}, Habilitado={is_enabled}")
        elif sensor_id == "NIBP":
            self.window.nibp.update_config(port, is_enabled)
            logger.info(f"[NIBP] Baumanómetro PAR NIBP2020 UP: Puerto={port}, Habilitado={is_enabled}")
