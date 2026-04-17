import unittest
import sys
from types import ModuleType
from unittest.mock import Mock, mock_open, patch

# Keep unit tests runnable even when third-party deps are not installed locally.
if "requests" not in sys.modules:
    requests_stub = ModuleType("requests")
    setattr(requests_stub, "post", lambda *args, **kwargs: None)
    sys.modules["requests"] = requests_stub

if "dotenv" not in sys.modules:
    dotenv_stub = ModuleType("dotenv")
    setattr(dotenv_stub, "load_dotenv", lambda: None)
    sys.modules["dotenv"] = dotenv_stub

import main


class TestBatteryLevel(unittest.TestCase):
    def test_get_battery_level_reads_bat0(self):
        with patch("builtins.open", mock_open(read_data="42\n")):
            self.assertEqual(main.get_battery_level(), 42)

    def test_get_battery_level_falls_back_to_bat1(self):
        bat1_file = mock_open(read_data="71\n")

        def open_side_effect(path, mode):
            if path == "/sys/class/power_supply/BAT0/capacity":
                raise FileNotFoundError
            if path == "/sys/class/power_supply/BAT1/capacity":
                return bat1_file.return_value
            raise AssertionError(f"Unexpected path: {path}")

        with patch("builtins.open", side_effect=open_side_effect):
            self.assertEqual(main.get_battery_level(), 71)


class TestSetSwitch(unittest.TestCase):
    @patch("main.print")
    @patch("main.requests.post")
    @patch("main.os.getenv")
    def test_set_switch_success(self, mock_getenv, mock_post, mock_print):
        mock_getenv.side_effect = lambda key: {
            "HAAS_URL": "http://ha.local",
            "ENTITY_ID": "switch.charger",
        }.get(key)
        mock_post.return_value = Mock(status_code=200, text="ok")

        with patch.dict(main.HEADERS, {"Authorization": "Bearer test"}, clear=False):
            main.set_switch("turn_on")

        mock_post.assert_called_once_with(
            "http://ha.local/api/services/switch/turn_on",
            headers=main.HEADERS,
            json={"entity_id": "switch.charger"},
        )
        mock_print.assert_called_once_with("Successfully sent turn_on command.")

    @patch("main.print")
    @patch("main.requests.post")
    @patch("main.os.getenv")
    def test_set_switch_error_response(self, mock_getenv, mock_post, mock_print):
        mock_getenv.side_effect = lambda key: {
            "HAAS_URL": "http://ha.local",
            "ENTITY_ID": "switch.charger",
        }.get(key)
        mock_post.return_value = Mock(status_code=500, text="boom")

        main.set_switch("turn_off")

        mock_print.assert_called_once_with("Error: 500 - boom")

    @patch("main.print")
    @patch("main.requests.post", side_effect=Exception("network down"))
    @patch("main.os.getenv")
    def test_set_switch_connection_failure(self, mock_getenv, _mock_post, mock_print):
        mock_getenv.side_effect = lambda key: {
            "HAAS_URL": "http://ha.local",
            "ENTITY_ID": "switch.charger",
        }.get(key)

        main.set_switch("turn_off")

        mock_print.assert_called_once_with("Connection failed: network down")


class TestUpdateAverageRates(unittest.TestCase):
    def test_update_average_rates_skips_first_sample(self):
        result = main.update_average_rates(
            None,
            None,
            50,
            1000,
            0.0,
            0,
            0.0,
            0,
        )
        self.assertEqual(result, (0.0, 0, 0.0, 0))

    def test_update_average_rates_tracks_charging(self):
        result = main.update_average_rates(
            50,
            0,
            53,
            1800,
            0.0,
            0,
            0.0,
            0,
        )
        self.assertEqual(result, (6.0, 1, 0.0, 0))

    def test_update_average_rates_tracks_discharging(self):
        result = main.update_average_rates(
            60,
            0,
            57,
            1800,
            0.0,
            0,
            0.0,
            0,
        )
        self.assertEqual(result, (0.0, 0, 6.0, 1))

    def test_update_average_rates_ignores_zero_elapsed_time(self):
        result = main.update_average_rates(
            60,
            1000,
            57,
            1000,
            1.0,
            1,
            2.0,
            1,
        )
        self.assertEqual(result, (1.0, 1, 2.0, 1))


if __name__ == "__main__":
    unittest.main()
