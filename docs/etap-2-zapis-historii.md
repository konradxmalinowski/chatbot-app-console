# Etap 2: Zapis historii rozmowy do pliku JSON

`last_updated: 2026-06-06`

## Problem

Historia rozmowy zyla wylacznie w pamieci operacyjnej (`InMemoryChatMessageHistory`). Kazde
zamkniecie programu powodowalo jej bezpowrotna utrate. Uzytkownik musial za kazdym razem
tlumaczyc kontekst od nowa.

## Nowy modul: `session_store.py`

Caly mechanizm utrwalania zostal wydzielony do osobnego pliku, co oddziela logike persystencji
od logiki czatu. Modul eksportuje dwie funkcje publiczne.

### `save_session`

Serializuje liste obiektow `BaseMessage` do pliku JSON:

```python
def save_session(
    session_id: str,
    messages: list[BaseMessage],
    sessions_dir: Path,
) -> None:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_id": session_id,
        "messages": [_message_to_dict(m) for m in messages],
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    session_file = sessions_dir / f"{session_id}.json"
    session_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

Katalog `sessions/` jest tworzony automatycznie przy pierwszym zapisie.

### `load_session`

Odczytuje plik i zwraca liste wiadomosci, lub pusta liste gdy plik nie istnieje:

```python
def load_session(session_id: str, sessions_dir: Path) -> list[BaseMessage]:
    session_file = sessions_dir / f"{session_id}.json"
    if not session_file.exists():
        return []
    try:
        raw = session_file.read_text(encoding="utf-8")
        payload = json.loads(raw)
        return [_dict_to_message(d) for d in payload.get("messages", [])]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning(
            "Could not load session %r (%s) — starting fresh.", session_id, exc
        )
        return []
```

## Format pliku JSON

Przyklad zawartosci `sessions/1.json` po krotniej rozmowie:

```json
{
  "session_id": "1",
  "messages": [
    { "role": "human", "content": "Czesc, jak masz na imie?" },
    { "role": "ai",    "content": "Jestem wirtualnym asystentem. Jak moge pomoc?" }
  ],
  "saved_at": "2026-06-06T10:15:00+00:00"
}
```

Pole `role` przyjmuje wartosci `"human"` lub `"ai"`. Nieznane role sa traktowane jako `"ai"`,
zeby historia nie zostala cicho utracona.

## Gdzie sa przechowywane pliki

Domyslna sciezka to `sessions/<session_id>.json` wzgledem katalogu roboczego.
Stala `SESSIONS_DIR` w `constants.py` kontroluje te lokalizacje:

```python
SESSIONS_DIR = Path("sessions")
```

## Kiedy nastepuje zapis

Zapis odbywa sie po wyjsciu z petli czatu (pusty monit), zaraz przed zakonczeniem programu:

```python
history = history_state.get(DEFAULT_SESSION_ID)
if history is not None:
    save_session(DEFAULT_SESSION_ID, history.get_messages(), SESSIONS_DIR)
    console.print("[dim]Session saved.[/]")
```

## Obsluga bledow

Jesli plik sesji istnieje, ale jest uszkodzony (nieprawidlowy JSON, brakujace klucze),
`load_session` przechwytuje wyjatek, loguje ostrzezenie i zwraca pusta liste. Aplikacja
startuje od nowa bez przerywania dzialania.
