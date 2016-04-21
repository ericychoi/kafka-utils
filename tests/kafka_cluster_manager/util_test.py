import pytest

from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import compute_optimum
from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import separate_groups


def test_compute_optimum():
    optimal, extra = compute_optimum(3, 10)

    assert optimal == 3
    assert extra == 1


def test_compute_optimum_zero_groups():
    with pytest.raises(ZeroDivisionError):
        optimal, extra = compute_optimum(0, 10)


def test_compute_optimum_zero_elements():
    optimal, extra = compute_optimum(10, 0)

    assert optimal == 0
    assert extra == 0


def test_separate_groups_balanced():
    groups = [4, 4, 4]
    total = 12

    overloaded, underloaded = separate_groups(groups, lambda x: x, total)

    assert not overloaded
    assert not underloaded


def test_separate_groups_almost_balanced():
    groups = [5, 5, 4]
    total = 14

    overloaded, underloaded = separate_groups(groups, lambda x: x, total)

    assert not overloaded
    assert not underloaded


def test_separate_groups_unbalanced():
    groups = [4, 4, 3, 2]
    total = 13

    overloaded, underloaded = separate_groups(groups, lambda x: x, total)

    assert overloaded == [4, 4]
    assert underloaded == [2]


def test_separate_groups_balanced_greater_total():
    groups = [4, 4, 4]
    total = 13

    overloaded, underloaded = separate_groups(groups, lambda x: x, total)

    assert underloaded == [4]


def test_separate_groups_balanced_much_greater_total():
    groups = [4, 4, 4]
    total = 20

    overloaded, underloaded = separate_groups(groups, lambda x: x, total)

    assert underloaded == [4, 4, 4]


def test_separate_groups_balanced_smaller_total():
    groups = [4, 4, 4]
    total = 6

    overloaded, underloaded = separate_groups(groups, lambda x: x, total)

    assert overloaded == [4, 4, 4]
