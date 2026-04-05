import json

from app.services.ltrc_processor import LTRCProcessor


def build_processor(tmp_path):
    processor = LTRCProcessor.__new__(LTRCProcessor)
    processor.point_distribution = [15, 13, 11, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    processor.FORMAT_CONFIGS = {
        "FFA": {"team_size": 1, "podium_count": 3, "max_players": 12},
        "2vs2": {"team_size": 2, "podium_count": 3, "max_players": 12},
        "3vs3": {"team_size": 3, "podium_count": 3, "max_players": 12},
        "4vs4": {"team_size": 4, "podium_count": 3, "max_players": 12},
        "5vs5": {"team_size": 5, "podium_count": 2, "max_players": 10},
        "6vs6": {"team_size": 6, "podium_count": 2, "max_players": 12},
    }
    processor.event_history_path = str(tmp_path / "player_event_history.json")
    return processor


def test_room_minimum_points_follow_room_size(tmp_path):
    processor = build_processor(tmp_path)

    assert processor._get_room_minimum_points(12) == 12
    assert processor._get_room_minimum_points(11) == 24
    assert processor._get_room_minimum_points(10) == 36


def test_initial_placement_mmr_is_linear_for_standard_rooms(tmp_path):
    processor = build_processor(tmp_path)

    assert processor._calculate_initial_placement_mmr(12, 12, {"32track": False}) == 1000
    assert processor._calculate_initial_placement_mmr(180, 12, {"32track": False}) == 3000
    assert processor._calculate_initial_placement_mmr(96, 12, {"32track": False}) == 2000


def test_initial_placement_mmr_normalizes_32track_scores(tmp_path):
    processor = build_processor(tmp_path)

    assert processor._calculate_initial_placement_mmr(480, 12, {"32track": True}) == 3000
    assert processor._calculate_initial_placement_mmr(32, 12, {"32track": True}) == 1000


def test_first_three_events_receive_boost_before_rounding(tmp_path):
    processor = build_processor(tmp_path)
    players = [
        {"tracked_event_count": 0},
        {"tracked_event_count": 2},
        {"tracked_event_count": 3},
    ]

    mmr_changes, new_mmrs = processor._calculate_mmr_changes(
        players=players,
        lr_list=[5000, 5000, 5000],
        k_values=[0, 0, 0],
        rankings=[1, 1, 1],
        mode="FFA",
        options={"32track": False, "200cc": False},
    )

    assert mmr_changes == [146, 146, 58]
    assert new_mmrs == [5146, 5146, 5058]


def test_event_history_tracks_each_event_once(tmp_path):
    processor = build_processor(tmp_path)
    history = processor._load_event_history()
    players = [{"name": "PlayerOne"}, {"name": "PlayerTwo"}]

    processor._record_tournament_participation(history, "LTRC_S1E1", players)
    processor._record_tournament_participation(history, "LTRC_S1E1", players)
    processor._save_event_history(history)

    with open(processor.event_history_path, "r") as history_file:
        saved_history = json.load(history_file)

    assert saved_history["playerone"]["events_played"] == 1
    assert saved_history["playerone"]["event_ids"] == ["LTRC_S1E1"]
    assert saved_history["playertwo"]["events_played"] == 1
