import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Navigate } from "react-router-dom";

import {
  generateImage,
  getNextEventId,
  getPlayerNames,
  getSessionState,
  logout,
  processWorkflow,
  updateSheets
} from "../lib/api";
import type {
  PlayerEntry,
  TournamentMode,
  TournamentResponse,
  WorkflowProcessRequest
} from "../lib/types";

type WorkflowStep = "setup" | "review" | "image" | "write" | "done";
type ImportableTournamentPayload = Partial<WorkflowProcessRequest> & {
  players?: Array<Partial<PlayerEntry>>;
};

const LIMIT_BREAKER_MODE = "Limit Breaker" as const;
const DEFAULT_PLAYER_ROWS = 12;
const DEFAULT_LIMIT_BREAKER_ROUNDS = 3;
const MODES: TournamentMode[] = [
  "FFA",
  "FFA KO",
  "2vs2",
  "2v2 GP",
  "3vs3",
  "4vs4",
  "5vs5",
  "6vs6",
  LIMIT_BREAKER_MODE
];
const MAX_PLAYERS_BY_MODE: Record<Exclude<TournamentMode, typeof LIMIT_BREAKER_MODE>, number> = {
  FFA: 12,
  "FFA KO": 12,
  "2vs2": 12,
  "2v2 GP": 12,
  "3vs3": 12,
  "4vs4": 12,
  "5vs5": 10,
  "6vs6": 12
};

function createEmptyPlayer(roundCount = DEFAULT_LIMIT_BREAKER_ROUNDS): PlayerEntry {
  return {
    name: "",
    score: "",
    mii_data: "",
    seed: "",
    round_scores: Array.from({ length: roundCount }, () => "")
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
  if (mode === "FFA" || mode === "FFA KO" || mode === LIMIT_BREAKER_MODE) {
    return "";
  }

  const teamSizeMap: Record<Exclude<TournamentMode, typeof LIMIT_BREAKER_MODE>, number> = {
    FFA: 1,
    "FFA KO": 1,
    "2vs2": 2,
    "2v2 GP": 2,
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

function isLimitBreakerMode(mode: TournamentMode): boolean {
  return mode === LIMIT_BREAKER_MODE;
}

function getMaxPlayersForMode(mode: TournamentMode): number {
  if (isLimitBreakerMode(mode)) {
    return Number.POSITIVE_INFINITY;
  }

  return MAX_PLAYERS_BY_MODE[mode as Exclude<TournamentMode, typeof LIMIT_BREAKER_MODE>];
}

function getMiiPreviewUrl(miiData: string): string | null {
  const trimmed = miiData.trim();
  if (!trimmed) {
    return null;
  }

  return `https://mii-unsecure.ariankordi.net/miis/image.png?data=${encodeURIComponent(trimmed)}&expression=normal&shaderType=switch&cameraYRotate=330`;
}

function applyBonuses(tournament: TournamentResponse): TournamentResponse {
  if (isLimitBreakerMode(tournament.mode)) {
    return tournament;
  }

  return {
    ...tournament,
    results: tournament.results.map((player) => ({
      ...player,
      mmr_change: player.mmr_change + player.bonus,
      new_mmr: player.new_mmr + player.bonus
    }))
  };
}

function buildAutoSubtitle(mode: TournamentMode, eventId: string, eventDate: string): string {
  if (isLimitBreakerMode(mode)) {
    return "Position | Round scores | Seed";
  }

  const match = eventId.match(/E(\d+)$/i);
  const eventNumber = match?.[1];
  return eventNumber ? `Event #${eventNumber} ${eventDate}` : `Event ${eventDate}`;
}

function isTournamentMode(value: string): value is TournamentMode {
  return MODES.includes(value as TournamentMode);
}

function normaliseImportedRoundScores(
  roundScores: unknown,
  fallbackScore: unknown,
  roundCount: number
): Array<number | ""> {
  if (Array.isArray(roundScores)) {
    return Array.from({ length: roundCount }, (_, index) => {
      const value = roundScores[index];
      return typeof value === "number" ? value : "";
    });
  }

  const score = typeof fallbackScore === "number" ? fallbackScore : "";
  return Array.from({ length: roundCount }, (_, index) => (index === 0 ? score : ""));
}

function buildPlayerRows(
  players: Array<Partial<PlayerEntry>>,
  targetRows: number,
  roundCount: number
): PlayerEntry[] {
  const importedRows: PlayerEntry[] = players.slice(0, targetRows).map((player) => ({
    name: typeof player.name === "string" ? player.name : "",
    score: player.score === "" || typeof player.score === "number" ? player.score : "",
    mii_data: typeof player.mii_data === "string" ? player.mii_data : "",
    seed: player.seed === null || player.seed === "" || typeof player.seed === "number" ? player.seed : "",
    round_scores: normaliseImportedRoundScores(player.round_scores, player.score, roundCount)
  }));

  return [
    ...importedRows,
    ...Array.from({ length: Math.max(0, targetRows - importedRows.length) }, () => createEmptyPlayer(roundCount))
  ];
}

function normalisePlayerForProcess(mode: TournamentMode, player: PlayerEntry): PlayerEntry {
  if (!isLimitBreakerMode(mode)) {
    return {
      ...player,
      seed: null,
      round_scores: []
    };
  }

  const roundScores = (player.round_scores ?? []).map((roundScore) => (roundScore === "" ? null : Number(roundScore)));
  const totalScore = roundScores.reduce<number>((total, roundScore) => total + (roundScore ?? 0), 0);

  return {
    ...player,
    score: totalScore,
    seed: player.seed === "" || player.seed === null ? null : Number(player.seed),
    round_scores: roundScores
  };
}

export function AppPage() {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<WorkflowStep>("setup");
  const [limitBreakerRoundCount, setLimitBreakerRoundCount] = useState(DEFAULT_LIMIT_BREAKER_ROUNDS);
  const [form, setForm] = useState<WorkflowProcessRequest>({
    event_id: "",
    mode: "FFA",
    players: Array.from({ length: DEFAULT_PLAYER_ROWS }, () => createEmptyPlayer(DEFAULT_LIMIT_BREAKER_ROUNDS)),
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

  const sessionQuery = useQuery({
    queryKey: ["session"],
    queryFn: getSessionState,
    retry: false
  });
  const nextEventIdQuery = useQuery({
    queryKey: ["next-event-id", form.mode],
    queryFn: () => getNextEventId(form.mode),
    enabled: Boolean(sessionQuery.data?.authenticated && sessionQuery.data.user?.authorized)
  });
  const playerNamesQuery = useQuery({
    queryKey: ["player-names"],
    queryFn: getPlayerNames,
    enabled: Boolean(
      sessionQuery.data?.authenticated &&
      sessionQuery.data.user?.authorized &&
      !isLimitBreakerMode(form.mode)
    )
  });

  const adjustedTournament = useMemo(
    () => (tournament ? applyBonuses(tournament) : null),
    [tournament]
  );
  const isLimitBreaker = isLimitBreakerMode(form.mode);
  const activePlayerSlots = isLimitBreaker ? form.players.length : getMaxPlayersForMode(form.mode);
  const visiblePlayers = useMemo(
    () => (isLimitBreaker ? form.players : form.players.slice(0, activePlayerSlots)),
    [activePlayerSlots, form.players, isLimitBreaker]
  );
  const activeRoundHeaders = useMemo(
    () => Array.from({ length: limitBreakerRoundCount }, (_, index) => `Round ${index + 1}`),
    [limitBreakerRoundCount]
  );
  const entryGridTemplateColumns = useMemo(
    () =>
      isLimitBreaker
        ? `72px minmax(0, 1.8fr) minmax(100px, 0.6fr) repeat(${limitBreakerRoundCount}, minmax(100px, 0.6fr))`
        : "72px minmax(0, 1.8fr) minmax(120px, 0.8fr)",
    [isLimitBreaker, limitBreakerRoundCount]
  );
  const filledPlayers = useMemo(() => {
    if (isLimitBreaker) {
      return form.players.filter((player) => player.name.trim() && player.seed !== "" && player.seed !== null);
    }

    return form.players
      .slice(0, activePlayerSlots)
      .filter((player) => player.name.trim() && player.score !== "");
  }, [activePlayerSlots, form.players, isLimitBreaker]);
  const hasPartialRows = useMemo(() => {
    return visiblePlayers.some((player) => {
      if (isLimitBreaker) {
        const hasRoundScore = (player.round_scores ?? []).some((roundScore) => roundScore !== "");
        const hasSeed = player.seed !== "" && player.seed !== null;
        const isUsed = Boolean(player.name.trim()) || hasSeed || hasRoundScore;
        if (!isUsed) {
          return false;
        }

        return !player.name.trim() || !hasSeed;
      }

      const hasName = Boolean(player.name.trim());
      const hasScore = player.score !== "";
      return hasName !== hasScore;
    });
  }, [isLimitBreaker, visiblePlayers]);
  const autoSubtitle = useMemo(
    () => (tournament ? buildAutoSubtitle(tournament.mode, tournament.event_id, tournament.event_date) : ""),
    [tournament]
  );
  const headerTitle = useMemo(() => {
    if (isLimitBreaker) {
      return "Limit Breaker Results";
    }

    const titleBits = [];
    if (form.options["32track"]) titleBits.push("32 Track");
    if (form.options["200cc"]) titleBits.push("200cc");
    if (form.options.ott) titleBits.push("OTT");
    titleBits.push(`${form.mode} Results`);
    return titleBits.join(" ");
  }, [form, isLimitBreaker]);
  const limitBreakerReviewRoundCount = useMemo(() => {
    if (!adjustedTournament || !isLimitBreakerMode(adjustedTournament.mode)) {
      return 0;
    }

    return adjustedTournament.results.reduce(
      (maxRounds, player) => Math.max(maxRounds, player.round_scores?.length ?? 0),
      0
    );
  }, [adjustedTournament]);

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
    mutationFn: async (payload: { tournament: TournamentResponse; persistImage: boolean; subtitle: string }) => {
      const shouldWriteSheets = !isLimitBreakerMode(payload.tournament.mode);
      return updateSheets({
        event_id: payload.tournament.event_id,
        results: shouldWriteSheets
          ? payload.tournament.results.map((player) => ({
              name: player.name,
              score: player.score,
              new_mmr: player.new_mmr,
              mmr_change: player.mmr_change,
              is_rated: player.is_rated,
              bonus: player.bonus
            }))
          : [],
        tournament: payload.tournament,
        persist_image: payload.persistImage,
        subtitle: payload.subtitle
      });
    },
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

  const isBusy =
    processMutation.isPending ||
    imageMutation.isPending ||
    writeMutation.isPending ||
    logoutMutation.isPending;

  if (sessionQuery.isLoading) {
    return <main className="page-shell"><section className="panel">Checking session...</section></main>;
  }

  if (!sessionQuery.data?.authenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!sessionQuery.data.user?.authorized) {
    return <Navigate to="/login?error=not_allowed" replace />;
  }

  const resetWorkflow = () => {
    if (imageUrl) {
      URL.revokeObjectURL(imageUrl);
    }
    setImageUrl(null);
    setTournament(null);
    setWorkflowError(null);
    setLimitBreakerRoundCount(DEFAULT_LIMIT_BREAKER_ROUNDS);
    setForm((current) => ({
      ...current,
      mode: "FFA",
      event_id: nextEventIdQuery.data?.event_id ?? current.event_id,
      players: Array.from({ length: DEFAULT_PLAYER_ROWS }, () => createEmptyPlayer(DEFAULT_LIMIT_BREAKER_ROUNDS)),
      options: {
        "32track": false,
        "200cc": false,
        ott: false
      }
    }));
    setStep("setup");
  };

  const updatePlayerBonus = (playerKey: string, bonusValue: number) => {
    setTournament((current) => {
      if (!current) {
        return current;
      }

      return {
        ...current,
        results: current.results.map((player) =>
          `${player.name}-${player.ranking}` === playerKey
            ? { ...player, bonus: bonusValue }
            : player
        )
      };
    });
  };

  const updatePlayer = (index: number, patch: Partial<PlayerEntry>) => {
    setForm((current) => ({
      ...current,
      players: current.players.map((player, playerIndex) =>
        playerIndex === index ? { ...player, ...patch } : player
      )
    }));
  };

  const updateRoundScore = (playerIndex: number, roundIndex: number, value: number | "") => {
    setForm((current) => ({
      ...current,
      players: current.players.map((player, index) => {
        if (index !== playerIndex) {
          return player;
        }

        const nextRoundScores = [...(player.round_scores ?? Array.from({ length: limitBreakerRoundCount }, () => ""))];
        nextRoundScores[roundIndex] = value;
        return {
          ...player,
          round_scores: nextRoundScores
        };
      })
    }));
  };

  const editPlayerMiiData = (playerIndex: number) => {
    const currentValue = form.players[playerIndex]?.mii_data ?? "";
    const nextValue = window.prompt(
      "Paste the player's Mii base64 data. Leave empty to clear it.",
      currentValue
    );

    if (nextValue === null) {
      return;
    }

    updatePlayer(playerIndex, { mii_data: nextValue.trim() });
  };

  const selectSuggestion = (rowIndex: number, suggestion: string) => {
    updatePlayer(rowIndex, { name: suggestion });
    setActiveAutocompleteIndex(null);
    setHighlightedSuggestionIndex(0);
  };

  const addLimitBreakerRound = () => {
    setLimitBreakerRoundCount((currentRoundCount) => {
      const nextRoundCount = currentRoundCount + 1;
      setForm((current) => ({
        ...current,
        players: current.players.map((player) => ({
          ...player,
          round_scores: [...(player.round_scores ?? Array.from({ length: currentRoundCount }, () => "")), ""]
        }))
      }));
      return nextRoundCount;
    });
  };

  const addLimitBreakerPlayer = () => {
    setForm((current) => ({
      ...current,
      players: [...current.players, createEmptyPlayer(limitBreakerRoundCount)]
    }));
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
      const importedRoundCount = isLimitBreakerMode(nextMode)
        ? Math.max(
            DEFAULT_LIMIT_BREAKER_ROUNDS,
            ...parsed.players.map((player) => Array.isArray(player.round_scores) ? player.round_scores.length : 0)
          )
        : limitBreakerRoundCount;
      const targetRows = isLimitBreakerMode(nextMode)
        ? Math.max(DEFAULT_PLAYER_ROWS, parsed.players.length)
        : getMaxPlayersForMode(nextMode);

      setLimitBreakerRoundCount(importedRoundCount);
      setForm((current) => ({
        ...current,
        mode: nextMode,
        event_date: typeof parsed.event_date === "string" ? parsed.event_date : current.event_date,
        options: isLimitBreakerMode(nextMode)
          ? { "32track": false, "200cc": false, ott: false }
          : {
              "32track": Boolean(parsed.options?.["32track"]),
              "200cc": Boolean(parsed.options?.["200cc"]),
              ott: Boolean(parsed.options?.ott)
            },
        players: buildPlayerRows(parsed.players ?? [], targetRows, importedRoundCount)
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
            <p className="support-copy">
              {isLimitBreaker
                ? "Enter Limit Breaker results manually with seeds and per-round scores."
                : "Enter results manually. Existing players autocomplete from the LTRC Sheet."}
            </p>
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
                    const nextIsLimitBreaker = isLimitBreakerMode(nextMode);
                    const targetRows = nextIsLimitBreaker ? current.players.length : DEFAULT_PLAYER_ROWS;
                    const nextPlayers = nextIsLimitBreaker
                      ? current.players.map((player) => ({
                          ...player,
                          round_scores:
                            player.round_scores && player.round_scores.length === limitBreakerRoundCount
                              ? player.round_scores
                              : Array.from({ length: limitBreakerRoundCount }, (_, index) => player.round_scores?.[index] ?? "")
                        }))
                      : current.players
                          .slice(0, DEFAULT_PLAYER_ROWS)
                          .map((player) => ({
                            ...player,
                            score: player.score,
                            round_scores:
                              player.round_scores && player.round_scores.length === limitBreakerRoundCount
                                ? player.round_scores
                                : Array.from({ length: limitBreakerRoundCount }, (_, index) => player.round_scores?.[index] ?? "")
                          }));

                    return {
                      ...current,
                      mode: nextMode,
                      options: nextIsLimitBreaker ? { "32track": false, "200cc": false, ott: false } : current.options,
                      players: [
                        ...nextPlayers,
                        ...Array.from({ length: Math.max(0, targetRows - nextPlayers.length) }, () => createEmptyPlayer(limitBreakerRoundCount))
                      ]
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
              {isLimitBreaker ? (
                <div className="action-row">
                  <button type="button" className="ghost-button" onClick={addLimitBreakerRound}>
                    Add Round
                  </button>
                  <button type="button" className="ghost-button" onClick={addLimitBreakerPlayer}>
                    Add Player
                  </button>
                </div>
              ) : null}
            </div>

            <div className="import-panel">
              <label className="stacked-label import-label">
                <span>Import Process JSON</span>
                <textarea
                  value={importJson}
                  onChange={(event) => setImportJson(event.target.value)}
                  placeholder="Paste exported JSON table here..."
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

            <div className="table-wrap">
              <div className="player-entry-grid player-entry-head" style={{ gridTemplateColumns: entryGridTemplateColumns }}>
                <span>Mii</span>
                <span>Player Name</span>
                {isLimitBreaker ? (
                  <>
                    <span>Seed</span>
                    {activeRoundHeaders.map((roundHeader) => (
                      <span key={roundHeader}>{roundHeader}</span>
                    ))}
                  </>
                ) : (
                  <span>Score</span>
                )}
              </div>

              <div className="player-entry-list">
                {visiblePlayers.map((player, index) => {
                const playerQuery = player.name.trim();
                const suggestions = isLimitBreaker ? [] : getNameSuggestions(playerNamesQuery.data?.players ?? [], player.name);
                const activeSuggestion = suggestions[highlightedSuggestionIndex];
                const teamClassName = getTeamClassName(form.mode, index);

                return (
                  <div
                    key={`player-row-${index}`}
                    className="player-entry-grid"
                    style={{ gridTemplateColumns: entryGridTemplateColumns }}
                  >
                    <div className="mii-field">
                      <button
                        type="button"
                        className={`mii-button ${player.mii_data ? "has-preview" : ""}`}
                        onClick={() => editPlayerMiiData(index)}
                      >
                        {player.mii_data ? (
                          <img
                            src={getMiiPreviewUrl(player.mii_data) ?? undefined}
                            alt={`${player.name || "Player"} Mii`}
                          />
                        ) : (
                          <span>Add</span>
                        )}
                      </button>
                    </div>
                    <div className="autocomplete-field">
                      <input
                        autoComplete="off"
                        className={teamClassName}
                        value={player.name}
                        onFocus={() => {
                          if (!isLimitBreaker) {
                            setActiveAutocompleteIndex(index);
                            setHighlightedSuggestionIndex(0);
                          }
                        }}
                        onBlur={() => {
                          window.setTimeout(() => {
                            setActiveAutocompleteIndex((current) => (current === index ? null : current));
                          }, 120);
                        }}
                        onChange={(event) => {
                          updatePlayer(index, { name: event.target.value });
                          if (!isLimitBreaker) {
                            setActiveAutocompleteIndex(index);
                            setHighlightedSuggestionIndex(0);
                          }
                        }}
                        onKeyDown={(event) => {
                          if (isLimitBreaker || activeAutocompleteIndex !== index || suggestions.length === 0) {
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
                      {!isLimitBreaker && activeAutocompleteIndex === index && playerQuery ? (
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
                    {isLimitBreaker ? (
                      <>
                        <input
                          autoComplete="off"
                          type="number"
                          value={player.seed ?? ""}
                          onChange={(event) =>
                            updatePlayer(index, {
                              seed: event.target.value === "" ? "" : Number(event.target.value)
                            })
                          }
                          placeholder="0"
                        />
                        {activeRoundHeaders.map((_, roundIndex) => (
                          <input
                            key={`round-${index}-${roundIndex}`}
                            autoComplete="off"
                            type="number"
                            value={player.round_scores?.[roundIndex] ?? ""}
                            onChange={(event) =>
                              updateRoundScore(
                                index,
                                roundIndex,
                                event.target.value === "" ? "" : Number(event.target.value)
                              )
                            }
                            placeholder="-"
                          />
                        ))}
                      </>
                    ) : (
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
                    )}
                  </div>
                );
                })}
              </div>
            </div>

            {hasPartialRows ? (
              <div className="notice-banner">
                {isLimitBreaker
                  ? "Complete both name and seed for each used row."
                  : "Complete both name and score for each used row."}
              </div>
            ) : null}
          </section>

          <div className="panel-footer">
            {!isLimitBreaker ? (
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
            ) : <div />}
            <button
              className="primary-button"
              disabled={
                isBusy ||
                nextEventIdQuery.isLoading ||
                (!isLimitBreaker && playerNamesQuery.isLoading) ||
                !form.event_id.trim() ||
                !form.event_date.trim() ||
                hasPartialRows ||
                filledPlayers.length === 0
              }
              onClick={() =>
                processMutation.mutate({
                  ...form,
                  players: filledPlayers.map((player) => normalisePlayerForProcess(form.mode, player))
                })
              }
            >
              {processMutation.isPending ? "Loading Tournament..." : "Start"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "review" && tournament && adjustedTournament ? (
        <section className="panel workflow-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Step 2</p>
              <h2>Review Results</h2>
            </div>
            <p className="support-copy">
              {isLimitBreakerMode(adjustedTournament.mode)
                ? "Check the derived rankings, rounds played, and totals before generating the image."
                : "Check that the calculated scores and rating changes look correct."}
            </p>
          </div>

          <div className="table-wrap">
            {isLimitBreakerMode(adjustedTournament.mode) ? (
              <table>
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Rank</th>
                    <th>Seed</th>
                    {Array.from({ length: limitBreakerReviewRoundCount }, (_, index) => (
                      <th key={`review-round-${index + 1}`}>Round {index + 1}</th>
                    ))}
                    <th>Rounds</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {adjustedTournament.results.map((player) => (
                    <tr key={`${player.name}-${player.ranking}`}>
                      <td>{player.name}</td>
                      <td>{player.ranking}</td>
                      <td>{player.seed ?? "-"}</td>
                      {Array.from({ length: limitBreakerReviewRoundCount }, (_, index) => (
                        <td key={`${player.name}-round-${index}`}>
                          {player.round_scores?.[index] ?? "-"}
                        </td>
                      ))}
                      <td>{player.rounds_played ?? 0}</td>
                      <td>{player.total_score ?? player.score}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Rank</th>
                    <th>Score</th>
                    <th>MMR</th>
                    <th>Boosted</th>
                    <th>Bonus</th>
                    <th>Change</th>
                    <th>New Rating</th>
                  </tr>
                </thead>
                <tbody>
                  {adjustedTournament.results.map((player, index) => {
                    const originalPlayer = tournament.results[index];
                    const playerKey = `${player.name}-${player.ranking}`;

                    return (
                      <tr key={playerKey}>
                        <td>{player.name}</td>
                        <td>{player.ranking}</td>
                        <td>{player.score}</td>
                        <td>{player.old_mmr < 0 ? "???" : player.old_mmr}</td>
                        <td>{player.boosted ? "Yes" : "No"}</td>
                        <td>
                          <input
                            type="number"
                            value={originalPlayer.bonus}
                            onFocus={(event) => event.target.select()}
                            onChange={(event) =>
                              updatePlayerBonus(
                                playerKey,
                                event.target.value === "" ? 0 : Number(event.target.value)
                              )
                            }
                            placeholder="0"
                          />
                        </td>
                        <td className={player.mmr_change >= 0 ? "positive" : "negative"}>
                          {player.mmr_change >= 0 ? `+${player.mmr_change}` : player.mmr_change}
                        </td>
                        <td>{player.new_mmr}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          <div className="action-row">
            <button className="ghost-button" onClick={() => setStep("setup")}>
              Back
            </button>
            <button
              className="primary-button"
              disabled={isBusy}
              onClick={() => setStep("image")}
            >
              Continue
            </button>
          </div>
        </section>
      ) : null}

      {step === "image" && adjustedTournament ? (
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
            {isLimitBreakerMode(adjustedTournament.mode)
              ? "Limit Breaker uses the manual-style subtitle from the new format config."
              : "The subtitle is generated automatically from the event number and date."}
          </p>

          <div className="action-row">
            <button className="ghost-button" onClick={() => setStep("review")}>
              Back
            </button>
            <button className="ghost-button" onClick={() => setStep("write")}>
              Skip Image Generation
            </button>
            <button
              className="primary-button"
              disabled={isBusy}
              onClick={() => imageMutation.mutate({ event_id: adjustedTournament.event_id, subtitle: autoSubtitle })}
            >
              {imageMutation.isPending ? "Generating Image..." : "Generate Image"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "write" && adjustedTournament ? (
        <section className="panel workflow-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Step 4</p>
              <h2>{isLimitBreakerMode(adjustedTournament.mode) ? "Save Results" : "Write Updated MMR"}</h2>
            </div>
            <p className="support-copy">
              {isLimitBreakerMode(adjustedTournament.mode)
                ? "Review the final state, then save the results and optional image."
                : "Review the final state, then write the new MMR values to the sheet."}
            </p>
          </div>

          {imageUrl ? (
            <div className="image-preview-card">
              <img className="image-preview" src={imageUrl} alt="Generated tournament result" />
              <div className="action-row">
                <a className="ghost-button link-button" href={imageUrl} download={`${adjustedTournament.event_id}.png`}>
                  Download Image
                </a>
              </div>
            </div>
          ) : (
            <div className="notice-banner">
              {isLimitBreakerMode(adjustedTournament.mode)
                ? "No image generated for this run. You can still save the results now."
                : "No image generated for this run. You can still write the MMR updates now."}
            </div>
          )}

          <div className="action-row">
            <button className="ghost-button" onClick={() => setStep("image")}>
              Back
            </button>
            <button
              className="primary-button"
              disabled={isBusy}
              onClick={() =>
                writeMutation.mutate({
                  tournament: adjustedTournament,
                  persistImage: Boolean(imageUrl),
                  subtitle: autoSubtitle
                })
              }
            >
              {writeMutation.isPending
                ? isLimitBreakerMode(adjustedTournament.mode) ? "Saving Results..." : "Writing To Sheets..."
                : isLimitBreakerMode(adjustedTournament.mode) ? "Save" : "Write"}
            </button>
          </div>
        </section>
      ) : null}

      {step === "done" ? (
        <section className="panel workflow-panel success-panel">
          <p className="eyebrow">Step 5</p>
          <h2>{adjustedTournament && isLimitBreakerMode(adjustedTournament.mode) ? "Results Saved Successfully" : "Sheet Updated Successfully"}</h2>
          <p className="support-copy">
            {adjustedTournament && isLimitBreakerMode(adjustedTournament.mode)
              ? "The Limit Breaker run is complete and the saved files are ready."
              : "The run is complete. You can start again immediately from the browser."}
          </p>
          <div className="action-row">
            <button className="ghost-button" onClick={() => setStep("write")}>
              Back
            </button>
            <button className="primary-button" onClick={resetWorkflow}>
              Restart
            </button>
          </div>
        </section>
      ) : null}
    </main>
  );
}
