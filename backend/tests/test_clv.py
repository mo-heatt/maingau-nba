"""Math of the CLV annuity."""
import pytest

from app.engine.utils import clv


def test_matches_manual_sum():
    expected = sum((200 - 30) * 0.9 ** (t - 1) / 1.06 ** t for t in range(1, 11))
    assert clv(200, 30, 0.10) == pytest.approx(expected)


def test_zero_churn_is_plain_discounted_annuity():
    expected = sum(170 / 1.06 ** t for t in range(1, 11))
    assert clv(200, 30, 0.0) == pytest.approx(expected)


def test_higher_churn_never_raises_clv():
    values = [clv(200, 30, c) for c in (0.0, 0.05, 0.3, 0.6, 0.9)]
    assert values == sorted(values, reverse=True)


def test_margin_equal_to_cost_means_zero():
    assert clv(30, 30, 0.1) == 0.0


def test_churn_is_clamped_to_valid_range():
    assert clv(200, 30, -0.5) == clv(200, 30, 0.0)
    assert clv(200, 30, 1.5) == clv(200, 30, 0.99)


def test_extreme_churn_keeps_the_first_year_payment():
    # churn applies from year 2 on ((1-churn)**(t-1)), so year 1 is always collected
    assert clv(200, 30, 0.99) == pytest.approx(170 / 1.06, abs=2.0)
