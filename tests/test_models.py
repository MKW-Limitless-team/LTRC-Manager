from datetime import datetime

from app.auth.models import SessionState, SessionUser
from app.models.base import ErrorResponse, ProcessingStatus, SheetsStatus
from app.models.image import SavedImageRequest
from app.models.ltrc import (
    PlayerData,
    TournamentOptions,
    TournamentRequest,
    TournamentResponse,
    TournamentResult,
    WorkflowProcessRequest,
)
from app.models.sheets import SheetsUpdateRequest, SheetsUpdateResult, SheetsUpdateResponse


def test_base_models_validate():
    error = ErrorResponse(error="Invalid request", code="VALIDATION", details={"field": "event_id"})
    processing = ProcessingStatus(
        status="ready",
        sheets_locked=False,
        locked_by=None,
        last_processed=datetime.now(),
        active_instances=1,
        supported_formats=["FFA", "FFA KO", "2vs2", "2v2 GP"],
    )
    sheets = SheetsStatus(
        connected=True,
        sheet_name="LTRC",
        locked=False,
        locked_by=None,
        last_update=None,
        error=None,
    )

    assert error.code == "VALIDATION"
    assert processing.supported_formats == ["FFA", "FFA KO", "2vs2", "2v2 GP"]
    assert sheets.connected is True


def test_tournament_request_and_options_aliases_work():
    request = TournamentRequest(
        event_id="LTRC_S1E1",
        mode="FFA KO",
        players=[PlayerData(name="Player1", score=120, mii_data="")],
        options={"32track": True, "200cc": False, "ott": True},
        event_date="31-01-2025",
    )

    assert request.options.three_two_track is True
    assert request.options.two_hundred_cc is False
    assert request.options.ott is True


def test_workflow_request_validates():
    workflow = WorkflowProcessRequest(
        event_id="LTRC_S1E5",
        mode="2v2 GP",
        options=TournamentOptions(),
        event_date="05-04-2026",
    )

    assert workflow.mode == "2v2 GP"
    assert workflow.event_id == "LTRC_S1E5"


def test_tournament_response_supports_rankings_and_options():
    response = TournamentResponse(
        event_id="LTRC_S1E3",
        mode="FFA",
        processed_at=datetime.now(),
        results=[
            TournamentResult(
                name="Player1",
                ranking=1,
                score=150,
                old_mmr=4200,
                new_mmr=4310,
                mmr_change=110,
                is_rated=True,
                mii_data="",
            )
        ],
        options=TournamentOptions(),
        event_date="05-04-2026",
    )

    assert response.results[0].ranking == 1
    assert response.options.ott is False


def test_sheets_models_validate():
    request = SheetsUpdateRequest(
        event_id="LTRC_S1E1",
        results=[SheetsUpdateResult(name="Player1", score=120, new_mmr=4300, mmr_change=100, is_rated=True)],
    )
    response = SheetsUpdateResponse(
        success=True,
        updated_cells=1,
        timestamp=datetime.now(),
        message="Sheet updated successfully",
    )

    assert request.results[0].name == "Player1"
    assert response.success is True


def test_auth_models_validate():
    state = SessionState(
        authenticated=True,
        user=SessionUser(
            id="123",
            display_name="Tester",
            avatar_url="https://cdn.discordapp.com/avatar.png",
            authorized=True,
        ),
    )

    assert state.authenticated is True
    assert state.user is not None
    assert state.user.display_name == "Tester"


def test_saved_image_request_accepts_optional_text():
    request = SavedImageRequest(event_id="LTRC_S1E10", subtitle="Week 10 Finals", title="FFA Results")

    assert request.event_id == "LTRC_S1E10"
    assert request.subtitle == "Week 10 Finals"
