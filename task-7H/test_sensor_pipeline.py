import unittest

from hardened_pipeline import (
    HardenedProcessor,
    Reading,
    moving_average,
    parse_line,
    read_with_retry,
    validate_reading,
)


class FakeSerial:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)

    def readline(self):
        value = next(self.outcomes)
        if isinstance(value, Exception):
            raise value
        return value


class PipelineTests(unittest.TestCase):
    def test_parse_valid_row(self):
        self.assertEqual(parse_line("2023,20.0,63.0"), Reading(2023, 20.0, 63.0))

    def test_reject_missing_field(self):
        with self.assertRaises(ValueError):
            parse_line("2023,,63.0")

    def test_reject_non_numeric_input(self):
        with self.assertRaises(ValueError):
            parse_line("abc,20.0,63.0")

    def test_reject_non_finite_input(self):
        with self.assertRaises(ValueError):
            parse_line("2023,nan,63.0")

    def test_reject_temperature_outlier(self):
        self.assertEqual(validate_reading(Reading(1, 80.0, 63.0))[0], False)

    def test_reject_humidity_outlier(self):
        self.assertEqual(validate_reading(Reading(1, 20.0, 150.0))[0], False)

    def test_moving_average(self):
        self.assertAlmostEqual(moving_average([20, 21, 22, 23, 24], 5), 22.0)

    def test_valid_pipeline_output(self):
        self.assertEqual(HardenedProcessor().process("2023,20.0,63.0")["status"], "valid")

    def test_degraded_pipeline_output(self):
        result = HardenedProcessor().process("2023,80.0,63.0")
        self.assertEqual(result["status"], "degraded")

    def test_stale_sequence(self):
        processor = HardenedProcessor(stale_limit=2)
        processor.process("1000,20.0,63.0")
        processor.process("2000,20.0,63.0")
        self.assertEqual(processor.process("3000,20.0,63.0")["reason"], "stale_sequence")

    def test_serial_recovers_after_two_failures(self):
        port = FakeSerial([OSError("disconnect"), OSError("disconnect"), b"2023,20.0,63.0\n"])
        result = read_with_retry(port, retries=3, retry_delay=0.001)
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["attempts"], 3)

    def test_serial_exhaustion_is_degraded(self):
        port = FakeSerial([OSError("disconnect")] * 3)
        result = read_with_retry(port, retries=3, retry_delay=0.001)
        self.assertEqual(result["status"], "degraded")


if __name__ == "__main__":
    unittest.main(verbosity=2)
