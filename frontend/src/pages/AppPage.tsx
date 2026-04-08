import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";

import { generateImage, getNextEventId, getPlayerNames, getSessionState, logout, processWorkflow, saveTournamentResults, updateSheets } from "../lib/api";
import type {
  PlayerEntry,
  SheetsUpdateRequest,
  TournamentMode,
  TournamentResponse,
  WorkflowProcessRequest
} from "../lib/types";

type WorkflowStep = "setup" | "review" | "image" | "write" | "done";
type ImportableTournamentPayload = Partial<WorkflowProcessRequest> & {
  players?: Array<Partial<PlayerEntry>>;
};

const MODES: TournamentMode[] = ["FFA", "2vs2", "3vs3", "4vs4", "5vs5", "6vs6"];
const MAX_PLAYER_ROWS = 12;
const MAX_PLAYERS_BY_MODE: Record<TournamentMode, number> = {
  FFA: 12,
  "2vs2": 12,
  "3vs3": 12,
  "4vs4": 12,
  "5vs5": 10,
  "6vs6": 12
};

function createEmptyPlayer(): PlayerEntry {
  return {
    name: "",
    score: "",
    mii_data: ""
  };
}

function getNameSuggestions(playerNames: string[], value: string): string[] {
  const query = value.trim().toLowerCase();
  if (!query) {
    return [];
  }

  return playerNames
    .filter((playerName) => playerName.toLowerCase().startsWith(query))
    .slice(0, 8);
}

function getTeamClassName(mode: TournamentMode, playerIndex: number): string {
  if (mode === "FFA") {
    return "";
  }

  const teamSizeMap: Record<TournamentMode, number> = {
    FFA: 1,
    "2vs2": 2,
    "3vs3": 3,
    "4vs4": 4,
    "5vs5": 5,
    "6vs6": 6
  };

  const teamSize = teamSizeMap[mode];
  const teamIndex = Math.floor(playerIndex / teamSize) % 6;
  return `team-${teamIndex + 1}`;
}

function todayAsDdMmYyyy(): string {
  const now = new Date();
  const day = `${now.getDate()}`.padStart(2, "0");
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  const year = now.getFullYear();
  return `${day}-${month}-${year}`;
}

function buildSheetsPayload(tournament: TournamentResponse): SheetsUpdateRequest {
  return {
    event_id: tournament.event_id,
    results: tournament.results.map((player) => ({
      name: player.name,
      score: player.score,
      new_mmr: player.new_mmr,
      mmr_change: player.mmr_change
    }))
  };
}

function buildAutoSubtitle(eventId: string, eventDate: string): string {
  const match = eventId.match(/E(\d+)$/i);
  const eventNumber = match?.[1];
  return eventNumber ? `Event #${eventNumber} ${eventDate}` : `Event ${eventDate}`;
}

function isTournamentMode(value: string): value is TournamentMode {
  return MODES.includes(value as TournamentMode);
}

function buildPlayerRows(players: Array<Partial<PlayerEntry>>, maxRows: number): PlayerEntry[] {
  const importedRows = players.slice(0, maxRows).map((player) => ({
    name: typeof player.name === "string" ? player.name : "",
    score: typeof player.score === "number" ? player.score : "",
    mii_data: typeof player.mii_data === "string" ? player.mii_data : ""
  }));

  return [
    ...importedRows,
    ...Array.from({ length: MAX_PLAYER_ROWS - importedRows.length }, createEmptyPlayer)
  ];
}

export function AppPage() {
  const queryClient = useQueryClient();
  const sessionQuery = useQuery({
    queryKey: ["session"],
    queryFn: getSessionState,
    retry: false
  });
  const nextEventIdQuery = useQuery({
    queryKey: ["next-event-id"],
    queryFn: getNextEventId,
    enabled: Boolean(sessionQuery.data?.authenticated && sessionQuery.data.user?.authorized)
  });
  const playerNamesQuery = useQuery({
    queryKey: ["player-names"],
    queryFn: getPlayerNames,
    enabled: Boolean(sessionQuery.data?.authenticated && sessionQuery.data.user?.authorized)
  });

  const [step, setStep] = useState<WorkflowStep>("setup");
  const [form, setForm] = useState<WorkflowProcessRequest>({
    event_id: "",
    mode: "FFA",
    players: Array.from({ length: MAX_PLAYER_ROWS }, createEmptyPlayer),
    event_date: todayAsDdMmYyyy(),
    options: {
      "32track": false,
      "200cc": false,
      ott: false
    }
  });
  const [tournament, setTournament] = useState<TournamentResponse | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [importJson, setImportJson] = useState("");
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [activeAutocompleteIndex, setActiveAutocompleteIndex] = useState<number | null>(null);
  const [highlightedSuggestionIndex, setHighlightedSuggestionIndex] = useState<number>(0);

  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageUrl]);

  useEffect(() => {
    if (nextEventIdQuery.data?.event_id) {
      setForm((current) => {
        if (current.event_id === nextEventIdQuery.data.event_id) {
          return current;
        }
        return { ...current, event_id: nextEventIdQuery.data.event_id };
      });
    }
  }, [nextEventIdQuery.data]);

  const processMutation = useMutation({
    mutationFn: processWorkflow,
    onSuccess: (response) => {
      setWorkflowError(null);
      setTournament(response);
      setStep("review");
    },
    onError: (error: Error) => setWorkflowError(error.message)
  });

  const imageMutation = useMutation({
    mutationFn: generateImage,
    onSuccess: (blob) => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
      const nextUrl = URL.createObjectURL(blob);
      setImageUrl(nextUrl);
      setWorkflowError(null);
      setStep("write");
    },
    onError: (error: Error) => setWorkflowError(error.message)
  });

  const writeMutation = useMutation({
    mutationFn: updateSheets,
    onSuccess: () => {
      setWorkflowError(null);
      setStep("done");
    },
    onError: (error: Error) => setWorkflowError(error.message)
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["session"] });
    }
  });
  const saveResultsMutation = useMutation({
    mutationFn: saveTournamentResults,
    onSuccess: () => {
      setWorkflowError(null);
      setStep("image");
    },
    onError: (error: Error) => setWorkflowError(error.message)
  });

  const headerTitle = useMemo(() => {
    const titleBits = [];
    if (form.options["32track"]) titleBits.push("32 Track");
    if (form.options["200cc"]) titleBits.push("200cc");
    if (form.options.ott) titleBits.push("OTT");
    titleBits.push(`${form.mode} Results`);
    return titleBits.join(" ");
  }, [form]);

  const filledPlayers = useMemo(
    () => form.players.filter((player) => player.name.trim() && player.score !== ""),
    [form.players]
  );
  const autoSubtitle = useMemo(
    () => (tournament ? buildAutoSubtitle(tournament.event_id, tournament.event_date) : ""),
    [tournament]
  );
  const activePlayerSlots = MAX_PLAYERS_BY_MODE[form.mode];
  const visiblePlayers = form.players.slice(0, activePlayerSlots);
  const hasPartialRows = useMemo(
    () => visiblePlayers.some((player) => {
      const hasName = Boolean(player.name.trim());
      const hasScore = player.score !== "";
      return hasName !== hasScore;
    }),
    [visiblePlayers]
  );

  if (sessionQuery.isLoading) {
    return <main className="page-shell"><section className="panel">Checking session...</section></main>;
  }

  if (!sessionQuery.data?.authenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!sessionQuery.data.user?.authorized) {
    return <Navigate to="/login?error=not_allowed" replace />;
  }

  const isBusy =
    processMutation.isPending ||
    imageMutation.isPending ||
    writeMutation.isPending ||
    logoutMutation.isPending ||
    saveResultsMutation.isPending;

  const resetWorkflow = () => {
    if (imageUrl) {
      URL.revokeObjectURL(imageUrl);
    }
    setImageUrl(null);
    setTournament(null);
    setWorkflowError(null);
    setForm((current) => ({
      ...current,
      event_id: nextEventIdQuery.data?.event_id ?? current.event_id,
      players: Array.from({ length: MAX_PLAYER_ROWS }, createEmptyPlayer)
    }));
    setStep("setup");
  };

  const updatePlayer = (index: number, patch: Partial<PlayerEntry>) => {
    setForm((current) => ({
      ...current,
      players: current.players.map((player, playerIndex) =>
        playerIndex === index ? { ...player, ...patch } : player
      )
    }));
  };

  const selectSuggestion = (rowIndex: number, suggestion: string) => {
    updatePlayer(rowIndex, { name: suggestion });
    setActiveAutocompleteIndex(null);
    setHighlightedSuggestionIndex(0);
  };

  const importFromJson = () => {
    try {
      const parsed = JSON.parse(importJson) as ImportableTournamentPayload;

      if (!parsed.mode || !isTournamentMode(parsed.mode)) {
        throw new Error("Imported JSON must include a valid tournament format.");
      }

      if (!Array.isArray(parsed.players)) {
        throw new Error("Imported JSON must include a players array.");
      }

      const nextMode = parsed.mode;
      const maxPlayers = MAX_PLAYERS_BY_MODE[nextMode];

      setForm((current) => ({
        ...current,
        mode: nextMode,
        event_date: typeof parsed.event_date === "string" ? parsed.event_date : current.event_date,
        options: {
          "32track": Boolean(parsed.options?.["32track"]),
          "200cc": Boolean(parsed.options?.["200cc"]),
          ott: Boolean(parsed.options?.ott)
        },
        players: buildPlayerRows(parsed.players ?? [], maxPlayers)
      }));

      setWorkflowError(null);
      setImportJson("");
      setActiveAutocompleteIndex(null);
      setHighlightedSuggestionIndex(0);
    } catch (error) {
      setWorkflowError(error instanceof Error ? error.message : "Failed to import tournament JSON.");
    }
  };

  return (
    <main className="app-shell">
      <header className="panel topbar">
        <div className="topbar-main">
          <div>
            <h1>LTRC Manager</h1>
          </div>
          <section className="progress-panel">
            <div className={`step-pill ${step === "setup" ? "active" : ""}`}>1. Setup</div>
            <div className={`step-pill ${step === "review" ? "active" : ""}`}>2. Review</div>
            <div className={`step-pill ${step === "image" ? "active" : ""}`}>3. Image</div>
            <div className={`step-pill ${step === "write" ? "active" : ""}`}>4. Write</div>
            <div className={`step-pill ${step === "done" ? "active" : ""}`}>5. Done</div>
          </section>
        </div>
        <div className="user-chip">
          {sessionQuery.data.user.avatar_url ? (
            <img src={sessionQuery.data.user.avatar_url} alt={sessionQuery.data.user.display_name} />
          ) : null}
          <span>{sessionQuery.data.user.display_name}</span>
          <button className="ghost-button" onClick={() => logoutMutation.mutate()}>
            Logout
          </button>
        </div>
      </header>

      {workflowError ? <div className="error-banner">{workflowError}</div> : null}

      {step === "setup" ? (
        <section className="panel workflow-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Step 1</p>
              <h2>Enter Tournament Data</h2>
            </div>
            <p className="support-copy">Enter results manually. Existing players autocomplete from the LTRC Sheet.</p>
          </div>

          <div className="form-grid">
            <label>
              <span>Event ID</span>
              <input
                value={form.event_id}
                readOnly
                className="readonly-input"
                placeholder={nextEventIdQuery.isLoading ? "Loading next event id..." : "LTRC_S5E1"}
              />
            </label>
            <label>
              <span>Event Date</span>
              <input
                value={form.event_date}
                onChange={(event) => setForm((current) => ({ ...current, event_date: event.target.value }))}
                placeholder="05-04-2026"
              />
            </label>
            <label>
              <span>Format</span>
              <select
                value={form.mode}
                onChange={(event) =>
                  setForm((current) => {
                    const nextMode = event.target.value as TournamentMode;
                    const nextMaxPlayers = MAX_PLAYERS_BY_MODE[nextMode];
                    return {
                      ...current,
                      mode: nextMode,
                      players: current.players.map((player, index) =>
                        index < nextMaxPlayers ? player : createEmptyPlayer()
                      )
                    };
                  })
                }
              >
                {MODES.map((mode) => (
                  <option key={mode} value={mode}>
                    {mode}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <section className="entry-panel">
            <div className="entry-panel-header">
              <div>
                <span className="eyebrow">Results Entry</span>
                <h3>Player Results</h3>
              </div>
            </div>

            <div className="import-panel">
              <label className="stacked-label import-label">
                <span>Import Process JSON</span>
                <textarea
                  value={importJson}
                  onChange={(event) => setImportJson(event.target.value)}
                  placeholder='Paste JSON like example_process.json here'
                  rows={6}
                />
              </label>
              <div className="import-actions">
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => setImportJson("")}
                  disabled={!importJson.trim()}
                >
                  Clear
                </button>
                <button
                  type="button"
                  className="primary-button"
                  onClick={importFromJson}
                  disabled={!importJson.trim()}
                >
                  Import
                </button>
              </div>
            </div>

            <div className="player-entry-grid player-entry-head">
              <span>Player Name</span>
              <span>Score</span>
            </div>

            <div className="player-entry-list">
              {visiblePlayers.map((player, index) => {
                const playerQuery = player.name.trim();
                const suggestions = getNameSuggestions(playerNamesQuery.data?.players ?? [], player.name);
                const activeSuggestion = suggestions[highlightedSuggestionIndex];
                const teamClassName = getTeamClassName(form.mode, index);

                return (
                  <div key={`player-row-${index}`} className="player-entry-grid">
                    <div className="autocomplete-field">
                      <input
                        autoComplete="off"
                        className={teamClassName}
                        value={player.name}
                        onFocus={() => {
                          setActiveAutocompleteIndex(index);
                          setHighlightedSuggestionIndex(0);
                        }}
                        onBlur={() => {
                          window.setTimeout(() => {
                            setActiveAutocompleteIndex((current) => (current === index ? null : current));
                          }, 120);
                        }}
                        onChange={(event) => {
                          updatePlayer(index, { name: event.target.value });
                          setActiveAutocompleteIndex(index);
                          setHighlightedSuggestionIndex(0);
                        }}
                        onKeyDown={(event) => {
                          if (activeAutocompleteIndex !== index || suggestions.length === 0) {
                            return;
                          }

                          if (event.key === "ArrowDown") {
                            event.preventDefault();
                            setHighlightedSuggestionIndex((current) => (current + 1) % suggestions.length);
                          } else if (event.key === "ArrowUp") {
                            event.preventDefault();
                            setHighlightedSuggestionIndex((current) => (
                              current - 1 < 0 ? suggestions.length - 1 : current - 1
                            ));
                          } else if (event.key === "Enter") {
                            if (activeSuggestion) {
                              event.preventDefault();
                              selectSuggestion(index, activeSuggestion);
                            }
                          } else if (event.key === "Tab") {
                            if (activeSuggestion) {
                              selectSuggestion(index, activeSuggestion);
                            }
                          } else if (event.key === "Escape") {
                            setActiveAutocompleteIndex(null);
                            setHighlightedSuggestionIndex(0);
                          }
                        }}
                        placeholder="Start typing a player name"
                      />
                      {activeAutocompleteIndex === index && playerQuery ? (
                        <div className="autocomplete-menu">
                          {suggestions.length > 0 ? (
                            suggestions.map((suggestion, suggestionIndex) => (
                              <button
                                key={`${index}-${suggestion}`}
                                type="button"
                                className={`autocomplete-option ${suggestionIndex === highlightedSuggestionIndex ? "active" : ""}`}
                                onMouseDown={() => {
                                  selectSuggestion(index, suggestion);
                                }}
                              >
                                {suggestion}
                              </button>
                            ))
                          ) : (
                            <div className="autocomplete-empty">
                              No existing player found. Press Enter to keep as a new player.
                            </div>
                          )}
                        </div>
                      ) : null}
                    </div>
                    <input
                      autoComplete="off"
                      className={teamClassName}
                      type="number"
                      value={player.score}
                      onChange={(event) =>
                        updatePlayer(index, {
                          score: event.target.value === "" ? "" : Number(event.target.value)
                        })
                      }
                      placeholder="0"
                    />
                  </div>
                );
              })}
            </div>

            {hasPartialRows ? (
              <div className="notice-banner">Complete both name and score for each used row.</div>
            ) : null}
          </section>

          <div className="panel-footer">
            <div className="checkbox-row footer-options">
              <button
                type="button"
                className={`toggle-card ${form.options["32track"] ? "active" : ""}`}
                aria-pressed={form.options["32track"]}
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    options: { ...current.options, "32track": !current.options["32track"] }
                  }))
                }
              >
                <span className="toggle-title">32 Track</span>
              </button>
              <button
                type="button"
                className={`toggle-card ${form.options["200cc"] ? "active" : ""}`}
                aria-pressed={form.options["200cc"]}
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    options: { ...current.options, "200cc": !current.options["200cc"] }
                  }))
                }
              >
                <span className="toggle-title">200cc</span>
              </button>
              <button
                type="button"
                className={`toggle-card ${form.options.ott ? "active" : ""}`}
                aria-pressed={form.options.ott}
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    options: { ...current.options, ott: !current.options.ott }
                  }))
                }
              >
                <span className="toggle-title">OTT</span>
              </button>
            </div>
            <button
              className="primary-button"
              disabled={
                isBusy ||
                nextEventIdQuery.isLoading ||
                playerNamesQuery.isLoading ||
                !form.event_id.trim() ||
                !form.event_date.trim() ||
                hasPartialRows ||
                filledPlayers.length === 0
              }
              onClick={() =>
                processMutation.mutate({
                  ...form,
                  players: filledPlayers as PlayerEntry[]
                })
              }
            >
              {processMutation.isPending ? "Loading Tournament..." : "Start"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "review" && tournament ? (
        <section className="panel workflow-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Step 2</p>
              <h2>Review Results</h2>
            </div>
            <p className="support-copy">Check that the calculated scores and rating changes look correct.</p>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Player</th>
                  <th>Rank</th>
                  <th>Score</th>
                  <th>MMR</th>
                  <th>Change</th>
                  <th>New Rating</th>
                </tr>
              </thead>
              <tbody>
                {tournament.results.map((player) => (
                  <tr key={`${player.name}-${player.ranking}`}>
                    <td>{player.name}</td>
                    <td>{player.ranking}</td>
                    <td>{player.score}</td>
                    <td>{player.old_mmr < 0 ? "???" : player.old_mmr}</td>
                    <td className={player.mmr_change >= 0 ? "positive" : "negative"}>
                      {player.mmr_change >= 0 ? `+${player.mmr_change}` : player.mmr_change}
                    </td>
                    <td>{player.new_mmr}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="action-row">
            <button className="ghost-button" onClick={resetWorkflow}>
              Refresh
            </button>
            <button
              className="primary-button"
              disabled={isBusy}
              onClick={() => tournament && saveResultsMutation.mutate(tournament)}
            >
              {saveResultsMutation.isPending ? "Saving Results..." : "Continue"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "image" && tournament ? (
        <section className="panel workflow-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Step 3</p>
              <h2>Image Generation</h2>
            </div>
            <p className="support-copy">{headerTitle}</p>
          </div>

          <label className="stacked-label">
            <span>Subtitle</span>
            <input
              value={autoSubtitle}
              readOnly
              className="readonly-input"
            />
          </label>

          <p className="helper-text">
            The subtitle is generated automatically from the event number and date.
          </p>

          <div className="action-row">
            <button className="ghost-button" onClick={() => setStep("write")}>
              Skip Image Generation
            </button>
            <button
              className="primary-button"
              disabled={isBusy}
              onClick={() => imageMutation.mutate({ event_id: tournament.event_id, subtitle: autoSubtitle })}
            >
              {imageMutation.isPending ? "Generating Image..." : "Generate Image"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "write" && tournament ? (
        <section className="panel workflow-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Step 4</p>
              <h2>Write Updated MMR</h2>
            </div>
            <p className="support-copy">Review the final state, then write the new MMR values to the sheet.</p>
          </div>

          {imageUrl ? (
            <div className="image-preview-card">
              <img className="image-preview" src={imageUrl} alt="Generated tournament result" />
              <div className="action-row">
                <a className="ghost-button link-button" href={imageUrl} download={`${tournament.event_id}.png`}>
                  Download Image
                </a>
              </div>
            </div>
          ) : (
            <div className="notice-banner">
              No image generated for this run. You can still write the MMR updates now.
            </div>
          )}

          <div className="action-row">
            <button className="ghost-button" onClick={() => setStep("image")}>
              Back
            </button>
            <button
              className="primary-button"
              disabled={isBusy}
              onClick={() => writeMutation.mutate(buildSheetsPayload(tournament))}
            >
              {writeMutation.isPending ? "Writing To Sheets..." : "Write"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "done" ? (
        <section className="panel workflow-panel success-panel">
          <p className="eyebrow">Step 5</p>
          <h2>Sheet Updated Successfully</h2>
          <p className="support-copy">The run is complete. You can start again immediately from the browser.</p>
          <button className="primary-button" onClick={resetWorkflow}>
            Restart
          </button>
        </section>
      ) : null}
    </main>
  );
}
