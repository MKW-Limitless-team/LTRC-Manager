from app.api.ltrc import _calculate_limit_breaker_results, get_event_json_path


def test_limit_breaker_rankings_prioritize_rounds_played_then_last_round_score():
    results = _calculate_limit_breaker_results(
        [
            {"name": "Alpha", "seed": 3, "round_scores": [70, 80, 60], "mii_data": ""},
            {"name": "Bravo", "seed": 8, "round_scores": [100, None, None], "mii_data": ""},
            {"name": "Charlie", "seed": 4, "round_scores": [60, 70, 90], "mii_data": ""},
            {"name": "Delta", "seed": 1, "round_scores": [90, 80, None], "mii_data": ""},
        ]
    )

    assert [player["name"] for player in results] == ["Charlie", "Alpha", "Delta", "Bravo"]
    assert [player["ranking"] for player in results] == [1, 2, 3, 4]
    assert results[0]["rounds_played"] == 3
    assert results[2]["rounds_played"] == 2
    assert results[3]["total_score"] == 100


def test_limit_breaker_rankings_allow_ties_within_same_round_count_group():
    results = _calculate_limit_breaker_results(
        [
            {"name": "Alpha", "seed": 3, "round_scores": [70, 80, None], "mii_data": ""},
            {"name": "Bravo", "seed": 8, "round_scores": [60, 80, None], "mii_data": ""},
            {"name": "Charlie", "seed": 4, "round_scores": [100, None, None], "mii_data": ""},
        ]
    )

    assert [player["ranking"] for player in results] == [1, 1, 3]


def test_limit_breaker_events_save_under_lb_directory():
    assert get_event_json_path("LB_14").endswith("database/LB/LB_14.json")
    assert get_event_json_path("LTRC_S5E3").endswith("database/LTRC_S5/LTRC_S5E3.json")
