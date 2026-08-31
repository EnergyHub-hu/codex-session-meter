# Changelog

A fájl a Codex Weekly Meter kiadásait dokumentálja.

A formátum a [Keep a Changelog](https://keepachangelog.com/hu/1.1.0/) alapján készült,
és a verziószámozás a [Semantic Versioning](https://semver.org/lang/hu/) elveit követi.

## [Unreleased]

## [v0.3.4] - 2026-08-31

### Új funkciók

- **Pace megjelenítési mód**: új `display_mode` beállítás `pace` és `absolute` értékekkel.
  - `pace`: a napi és heti fogyasztás ütemét jeleníti meg százalékban.
  - `absolute`: az eredeti viszonylagos megjelenítés.
- **Per-component panel visibility**: a panel komponensei (`show_session`, `show_daily`, `show_weekly`) külön-külön kapcsolhatók.
- **Session pace**: az 5 órás munkamenet ütemének számítása és megjelenítése.
- **Daily indicator színek**: gradiens alapú hex színkódolás a napi limit jelzőhöz (helyettesíti a HSL megoldást).
- **Warm palette**: a limit indicator színskálája meleg színekre váltott.
- **Pace normalizáció és szín-interpoláció**: a pace értékek normalizálása és színekkel való megjelenítése.
- **Elapsed workdays**: a `startedWorkdays` mező lecserélve `elapsedWorkdays`-re a proporciónális időkövetéshez.
- **AGENTS.md fájlok**: új útmutató fájlok a repository, helper és extension könyvtárakhoz.
- **Debug CLI**: a `codex-session-meter debug` diagnosztikai nézetet biztosít
  `--no-color`, `--width` és `--copy` opciókkal.

### Refaktorálás

- **Visibility flags**: a `display_format` beállítás lecserélve boolean `show_session`, `show_daily`, `show_weekly` flag-ekre.
- **Payload pipeline**: a visibility flag-ek átvezetése a teljes payload pipeline-on.

### Javítások

- **Fetch migration**: a `display_format` → visibility flags migráció befejezése a fetcher modulban.

### Stílus

- **Color scale**: a limit indicator színskálája meleg színekre váltott.

## [v0.3.1] - 2025

### Javítások

- Korábbi hibák javítása.

## [v0.3.0] - 2025

### Új funkciók

- Heti kvóta követés.
- GNOME Shell extension a felső panelen.
- Helper Python CLI csomag.

---

## Verziószámozás

- ** GNOME extension**: a `metadata.json` `version` mezője (egész szám).
- **Helper**: semantic versioning a `setuptools-scm` segítségével.
