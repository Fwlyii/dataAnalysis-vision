"""Dispatch accounting tests; no model calls or credentials."""
import threading
import unittest

from experiments.code_repair_v2.src.collect import Lane


class DispatchTests(unittest.TestCase):
    def lane(self):
        return Lane({'initial_rpm': 300, 'initial_tpm': 200000,
                     'maximum_rpm': 600, 'maximum_tpm': 220000}, threading.Event())

    def test_success_keeps_provider_reservation_and_honors_larger_actual(self):
        lane = self.lane()
        first = lane.acquire(3000)
        lane.observe(first, {'total_tokens': 700}, 200)
        self.assertEqual(first[1], 3000)
        second = lane.acquire(1000)
        lane.observe(second, {'total_tokens': 1200}, 200)
        self.assertEqual(second[1], 1200)

    def test_rejected_requests_release_tokens_but_unknown_transport_keeps_them(self):
        lane = self.lane()
        rejected = lane.acquire(3000)
        lane.observe(rejected, {}, 429, error='TPM limit reached')
        self.assertEqual(rejected[1], 0)
        unknown = [0, 3000]
        lane.observe(unknown, {}, None, error='TimeoutError')
        self.assertEqual(unknown[1], 3000)

    def test_fixed_tpm_does_not_grow_after_fifty_successes(self):
        lane = self.lane()
        lane.grow_tpm = False
        for _ in range(50):
            lane.observe([0, 1000], {'total_tokens': 100}, 200)
        self.assertEqual(lane.tpm, 200000)
        self.assertGreater(lane.rpm, 300)

    def test_oversized_reservation_fails_instead_of_waiting_forever(self):
        lane = self.lane()
        with self.assertRaisesRegex(RuntimeError, 'dispatch TPM budget'):
            lane.acquire(200001)

    def test_simultaneous_tpm_rejections_reduce_once_and_do_not_reduce_rpm(self):
        lane = self.lane()
        for _ in range(20):
            lane.observe([0, 1000], {}, 429, error='TPM limit reached')
        self.assertEqual(lane.tpm, 160000)
        self.assertEqual(lane.rpm, 300)
        self.assertEqual(lane.ratelimits, 20)


if __name__ == '__main__':
    unittest.main()
