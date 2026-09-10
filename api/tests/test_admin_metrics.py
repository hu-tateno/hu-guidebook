from app.services.admin_metrics import compute_evaluation_stats


def test_compute_evaluation_stats_basic_rates():
    stats = compute_evaluation_stats(
        total_searches=10, helpful_flags=[True, True, False], resolved_flags=[True, False]
    )
    assert stats.total_searches == 10
    assert stats.total_evaluations == 3
    assert stats.helpful_rate == 2 / 3
    assert stats.resolved_rate == 0.5


def test_compute_evaluation_stats_no_evaluations_yields_none_rates():
    stats = compute_evaluation_stats(total_searches=5, helpful_flags=[], resolved_flags=[])
    assert stats.total_evaluations == 0
    assert stats.helpful_rate is None
    assert stats.resolved_rate is None


def test_compute_evaluation_stats_all_helpful():
    stats = compute_evaluation_stats(total_searches=1, helpful_flags=[True, True], resolved_flags=[])
    assert stats.helpful_rate == 1.0
    assert stats.resolved_rate is None
