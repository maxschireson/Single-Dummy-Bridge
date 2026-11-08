import unittest
from collection_slices import bounded_slice, SliceComplete


class SliceTests(unittest.TestCase):
    def test_drain_and_stop(self):
        clock = [0]
        seen = []
        def work(n):
            seen.append(n)
            clock[0] = 10
            return n
        with self.assertRaises(SliceComplete):
            list(bounded_slice(work, range(20), 1, 5, lambda: clock[0]))
        self.assertEqual(seen, [0])

    def test_finish_last_board_after_deadline(self):
        clock = [0]
        def work(n):
            clock[0] = 10
            return n
        self.assertEqual(list(bounded_slice(work, [1], 1, 5, lambda: clock[0])), [1])

    def test_errors_are_not_retried(self):
        def work(n):
            raise ValueError('invalid record')
        with self.assertRaisesRegex(ValueError, 'invalid record'):
            list(bounded_slice(work, range(20), 1, 5, lambda: 0))

    def test_all_jobs(self):
        self.assertEqual(sorted(bounded_slice(lambda n: n, range(20), 3, 5, lambda: 0)), list(range(20)))


if __name__ == '__main__':
    unittest.main()
