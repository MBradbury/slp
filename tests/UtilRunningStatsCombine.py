from __future__ import print_function, division

import unittest

import numpy as np

from data.util import RunningStats

class TestUtilRunningStatsCombine(unittest.TestCase):

    def test_simple(self):
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        stats = RunningStats()
        for item in data:
            stats.push(item)

        self.assertEqual(stats.n, len(data))
        self.assertEqual(stats.mean(), np.mean(data))
        self.assertEqual(stats.var(), np.var(data, ddof=1))
        self.assertEqual(stats.stddev(), np.std(data, ddof=1))

    def test_merge(self):
        data1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        data2 = [5.5] * 20

        data3 = data1 + data2

        stats1 = RunningStats()
        for item in data1:
            stats1.push(item)

        stats2 = RunningStats()
        for item in data2:
            stats2.push(item)

        stats12 = stats1.combine(stats2)

        stats3 = RunningStats()
        for item in data3:
            stats3.push(item)

        self.assertEqual(stats1.n + stats2.n, stats12.n)
        self.assertEqual(stats3.n, stats12.n)
        self.assertEqual(stats3.mean(), stats12.mean())
        self.assertEqual(stats3.var(), stats12.var())
        self.assertEqual(stats3.stddev(), stats12.stddev())

        for ddof in [0, 1, 2, 3]:
            self.assertEqual(stats12.n, len(data3))
            self.assertEqual(stats12.mean(), np.mean(data3))
            self.assertEqual(stats12.var(ddof=ddof), np.var(data3, ddof=ddof))
            self.assertEqual(stats12.stddev(ddof=ddof), np.std(data3, ddof=ddof))


if __name__ == "__main__":
    unittest.main()
