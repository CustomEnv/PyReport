"""Tests for error grouping analyzer."""
from __future__ import annotations

from pyreport.analyzers.grouper import (
    group_failures,
    hash_traceback,
    normalize_traceback,
)
from pyreport.core import Status, TestCase, TestRun, TestSuite


class TestNormalizeTraceback:
    def test_none_or_empty(self):
        assert normalize_traceback("") == ""
        assert normalize_traceback(None) == ""

    def test_normalizes_line_numbers(self):
        tb = '  File "x.py", line 42, in foo\n    assert False'
        result = normalize_traceback(tb)
        assert "line N" in result
        assert "line 42" not in result

    def test_normalizes_addresses(self):
        tb = "ValueError at 0x7f8e2c0b5b80"
        result = normalize_traceback(tb)
        assert "0xH" in result
        assert "0x7f8e2c0b5b80" not in result

    def test_normalizes_strings(self):
        tb = """assert "hello" == "world" """
        result = normalize_traceback(tb)
        assert '"S"' in result
        assert '"hello"' not in result

    def test_normalizes_numbers(self):
        tb = "assert 1 == 2"
        result = normalize_traceback(tb)
        assert "N" in result
        assert "1 == 2" not in result

    def test_same_error_normalizes_equally(self):
        tb1 = 'assert 1 == 2\n  File "test.py", line 42, in foo'
        tb2 = 'assert 99 == 100\n  File "test.py", line 99, in foo'
        assert normalize_traceback(tb1) == normalize_traceback(tb2)

    def test_different_errors_different_normalized(self):
        tb1 = "ValueError: bad value"
        tb2 = "TypeError: wrong type"
        assert normalize_traceback(tb1) != normalize_traceback(tb2)


class TestHashTraceback:
    def test_returns_consistent_hash(self):
        tb = "ValueError('x')\n  File test.py:42"
        h1 = hash_traceback(tb)
        h2 = hash_traceback(tb)
        assert h1 == h2
        assert len(h1) == 16  # truncated sha256

    def test_same_error_same_hash(self):
        tb1 = 'assert 1 == 2\n  File "test.py", line 42'
        tb2 = 'assert 99 == 100\n  File "test.py", line 99'
        assert hash_traceback(tb1) == hash_traceback(tb2)

    def test_different_error_different_hash(self):
        tb1 = "ValueError: bad"
        tb2 = "TypeError: bad"
        assert hash_traceback(tb1) != hash_traceback(tb2)

    def test_none_returns_none(self):
        assert hash_traceback(None) is None
        assert hash_traceback("") is None


class TestGroupFailures:
    def test_groups_identical_errors(self):
        run = TestRun(
            id="r1",
            suites=[
                TestSuite(
                    id="s1", name="s1", duration=0, status=Status.FAILED,
                    tests=[
                        TestCase(id="c1", name="test_a", full_name="mod::test_a",
                                 duration=0, status=Status.FAILED,
                                 message="AssertionError",
                                 traceback='assert 1 == 2\n  File "t.py", line 5'),
                        TestCase(id="c2", name="test_b", full_name="mod::test_b",
                                 duration=0, status=Status.FAILED,
                                 message="AssertionError",
                                 traceback='assert 1 == 2\n  File "t.py", line 99'),
                        TestCase(id="c3", name="test_c", full_name="mod::test_c",
                                 duration=0, status=Status.PASSED),
                    ],
                ),
            ],
        )
        groups = group_failures(run)
        assert len(groups) == 1
        assert groups[0].count == 2

    def test_separates_different_errors(self):
        run = TestRun(
            id="r1",
            suites=[
                TestSuite(
                    id="s1", name="s1", duration=0, status=Status.FAILED,
                    tests=[
                        TestCase(id="c1", name="test_a", full_name="mod::test_a",
                                 duration=0, status=Status.FAILED,
                                 traceback="ValueError: bad"),
                        TestCase(id="c2", name="test_b", full_name="mod::test_b",
                                 duration=0, status=Status.FAILED,
                                 traceback="TypeError: bad"),
                    ],
                ),
            ],
        )
        groups = group_failures(run)
        assert len(groups) == 2

    def test_skips_passed_tests(self):
        run = TestRun(
            id="r1",
            suites=[
                TestSuite(
                    id="s1", name="s1", duration=0, status=Status.PASSED,
                    tests=[
                        TestCase(id="c1", name="test_a", full_name="mod::test_a",
                                 duration=0, status=Status.PASSED),
                    ],
                ),
            ],
        )
        assert group_failures(run) == []

    def test_returns_sorted_by_count(self):
        run = TestRun(
            id="r1",
            suites=[
                TestSuite(
                    id="s1", name="s1", duration=0, status=Status.FAILED,
                    tests=[
                        TestCase(id=f"c{i}", name=f"test_{i}", full_name=f"mod::test_{i}",
                                 duration=0, status=Status.FAILED,
                                 traceback="ValueError: bad" if i < 2 else "TypeError: bad")
                        for i in range(5)
                    ],
                ),
            ],
        )
        groups = group_failures(run)
        assert len(groups) >= 1
        # Most frequent group first
        assert groups[0].count >= groups[-1].count if len(groups) > 1 else True
