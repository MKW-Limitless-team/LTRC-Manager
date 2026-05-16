import json

from app.services.ltrc_processor import LTRCProcessor


def build_processor(tmp_path):
    processor = LTRCProcessor.__new__(LTRCProcessor)
    processor.point_distribution = [15, 13, 11, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    processor.FORMAT_CONFIGS = {
        "FFA": {"team_size": 1, "podium_count": 3, "max_players": 12},
        "FFA KO": {"team_size": 1, "podium_count": 3, "max_players": 12},
        "2vs2": {"team_size": 2, "podium_count": 3, "max_players": 12},
        "2v2 GP": {"team_size": 2, "podium_count": 3, "max_players": 12},
        "3vs3": {"team_size": 3, "podium_count": 3, "max_players": 12},
        "4vs4": {"team_size": 4, "podium_count": 3, "max_players": 12},
        "5vs5": {"team_size": 5, "podium_count": 2, "max_players": 10},
        "6vs6": {"team_size": 6, "podium_count": 2, "max_players": 12},
    }
    processor.NON_PLACEMENT_MODES = {"FFA KO", "2v2 GP"}
    processor.event_history_path = str(tmp_path / "player_event_history.json")
    return processor


def stub_sheet_dependencies(processor, mmr_by_name):
    processor.refresh_playerdata_cache = lambda: None
    processor._ensure_players_exist = lambda players: None
    processor._get_player_mmr_from_sheets = lambda name: mmr_by_name.get(name)


class FakePlayerdataSheet:
    def __init__(self, rows):
        self.rows = rows
        self.get_all_values_calls = 0

    def get_all_values(self):
        self.get_all_values_calls += 1
        return self.rows


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


def test_processing_refreshes_playerdata_cache_before_reading_mmr(tmp_path):
    processor = build_processor(tmp_path)
    processor.playerdata_cache = [["PlayerOne", "", "", "1200"], ["PlayerTwo", "", "", "1300"]]
    processor.Playerdata = FakePlayerdataSheet(
        [["PlayerOne", "", "", "2600"], ["PlayerTwo", "", "", "2700"]]
    )

    result = processor.process_tournament(
        event_id="LTRC_S1E9",
        mode="FFA",
        players=[
            {"name": "PlayerOne", "score": 120, "mii_data": ""},
            {"name": "PlayerTwo", "score": 100, "mii_data": ""},
        ],
        options={"32track": False, "200cc": False},
        event_date="18-04-2026",
    )

    assert processor.Playerdata.get_all_values_calls == 1
    assert [player["old_mmr"] for player in result["results"]] == [2600, 2700]


def test_player_mmr_lookup_trims_names_and_ignores_case(tmp_path):
    processor = build_processor(tmp_path)
    processor.playerdata_cache = [["  SheetName  ", "", "", "2400"]]

    assert processor._get_player_mmr_from_sheets("sheetname") == 2400


def test_non_placement_modes_use_2000_seed_and_keep_players_unrated(tmp_path):
    processor = build_processor(tmp_path)
    stub_sheet_dependencies(processor, {})

    result = processor.process_tournament(
        event_id="LTRC_S1E10",
        mode="FFA KO",
        players=[
            {"name": "PlayerOne", "score": 999, "mii_data": ""},
            {"name": "PlayerTwo", "score": 700, "mii_data": ""},
        ],
        options={"32track": False, "200cc": False},
        event_date="18-04-2026",
    )

    assert [player["old_mmr"] for player in result["results"]] == [-1, -1]
    assert [player["is_rated"] for player in result["results"]] == [False, False]
    assert all(isinstance(player["mmr_change"], int) for player in result["results"])
    assert all(isinstance(player["new_mmr"], int) for player in result["results"])
    assert not tmp_path.joinpath("player_event_history.json").exists()


def test_standard_modes_still_rate_unranked_players_from_placement_seed(tmp_path):
    processor = build_processor(tmp_path)
    stub_sheet_dependencies(processor, {})

    result = processor.process_tournament(
        event_id="LTRC_S1E11",
        mode="FFA",
        players=[
            {"name": "PlayerOne", "score": 180, "mii_data": ""},
            {"name": "PlayerTwo", "score": 12, "mii_data": ""},
        ],
        options={"32track": False, "200cc": False},
        event_date="18-04-2026",
    )

    assert [player["old_mmr"] for player in result["results"]] == [-1, -1]
    assert [player["is_rated"] for player in result["results"]] == [True, True]
    assert result["results"][0]["new_mmr"] > result["results"][1]["new_mmr"]


def test_non_placement_modes_skip_score_cap_validation(tmp_path):
    processor = build_processor(tmp_path)
    stub_sheet_dependencies(processor, {"RatedOne": 2500, "RatedTwo": 2500})

    result = processor.process_tournament(
        event_id="LTRC_S1E12",
        mode="FFA KO",
        players=[
            {"name": "RatedOne", "score": 999, "mii_data": ""},
            {"name": "RatedTwo", "score": 700, "mii_data": ""},
        ],
        options={"32track": False, "200cc": False},
        event_date="18-04-2026",
    )

    assert len(result["results"]) == 2


def test_standard_modes_keep_existing_score_cap_validation(tmp_path):
    processor = build_processor(tmp_path)
    stub_sheet_dependencies(processor, {"RatedOne": 2500, "RatedTwo": 2500})

    try:
        processor.process_tournament(
            event_id="LTRC_S1E13",
            mode="FFA",
            players=[
                {"name": "RatedOne", "score": 181, "mii_data": ""},
                {"name": "RatedTwo", "score": 12, "mii_data": ""},
            ],
            options={"32track": False, "200cc": False},
            event_date="18-04-2026",
        )
    except ValueError as exc:
        assert "exceeds maximum for normal events" in str(exc)
    else:
        raise AssertionError("Expected standard FFA to reject scores above 180")


def test_2v2_gp_rankings_and_team_deltas_match_2vs2(tmp_path):
    processor = build_processor(tmp_path)
    scores = [100, 80, 70, 60]

    assert processor._find_rankings(scores, "2v2 GP") == processor._find_rankings(scores, "2vs2")

    rankings = processor._find_rankings(scores, "2v2 GP")
    k_values = processor._get_k_values(rankings, "2v2 GP")
    mmr_changes, _ = processor._calculate_mmr_changes(
        players=[
            {"tracked_event_count": 3},
            {"tracked_event_count": 3},
            {"tracked_event_count": 3},
            {"tracked_event_count": 3},
        ],
        lr_list=[2100, 1900, 2300, 1700],
        k_values=k_values,
        rankings=rankings,
        mode="2v2 GP",
        options={"32track": False, "200cc": False},
    )

    assert rankings == [1, 1, 2, 2]
    assert mmr_changes[0] == mmr_changes[1]
    assert mmr_changes[2] == mmr_changes[3]


def test_ffa_ko_rankings_use_scores_and_allow_ties(tmp_path):
    processor = build_processor(tmp_path)

    rankings = processor._find_rankings([6, 6, 4, 2], "FFA KO")

    assert rankings == [1, 1, 3, 4]


def test_event_history_is_only_persisted_on_final_write(tmp_path):
    processor = build_processor(tmp_path)
    stub_sheet_dependencies(processor, {"PlayerOne": 2500, "PlayerTwo": 2400})

    result = processor.process_tournament(
        event_id="LTRC_S1E14",
        mode="FFA",
        players=[
            {"name": "PlayerOne", "score": 120, "mii_data": ""},
            {"name": "PlayerTwo", "score": 100, "mii_data": ""},
        ],
        options={"32track": False, "200cc": False},
        event_date="19-04-2026",
    )

    assert not tmp_path.joinpath("player_event_history.json").exists()

    processor.record_event_history("LTRC_S1E14", result["results"])
    processor.record_event_history("LTRC_S1E14", result["results"])

    with open(processor.event_history_path, "r") as history_file:
        saved_history = json.load(history_file)

    assert saved_history["playerone"]["events_played"] == 1
    assert saved_history["playertwo"]["events_played"] == 1
