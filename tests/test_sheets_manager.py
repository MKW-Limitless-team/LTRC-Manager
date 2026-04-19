from types import SimpleNamespace

from app.services.sheets_manager import SheetsManager


class FakePlayerdataSheet:
    def __init__(self):
        self.rows_by_name = {"RatedPlayer": 2, "UnratedPlayer": 3}
        self.updated_cells = []

    def find(self, player_name, case_sensitive=False):
        row = self.rows_by_name.get(player_name)
        if row is None:
            return None
        return SimpleNamespace(row=row)

    def update_cell(self, row, column, value):
        self.updated_cells.append((row, column, value))


def test_update_playerdata_sheet_skips_unrated_results():
    manager = SheetsManager.__new__(SheetsManager)
    manager.Playerdata = FakePlayerdataSheet()

    updated_cells = manager._update_playerdata_sheet(
        event_id="LTRC_S1E1",
        results=[
            {"name": "RatedPlayer", "new_mmr": 3100, "is_rated": True},
            {"name": "UnratedPlayer", "new_mmr": 2050, "is_rated": False},
        ],
    )

    assert updated_cells == 1
    assert manager.Playerdata.updated_cells == [(2, 4, 3100)]
