# Etap 1: Wybor modelu przez argument CLI

`last_updated: 2026-06-06`

## Problem

W pierwotnej wersji aplikacji model jezykowy byl okreslony wylacznie przez zmienna srodowiskowa
`GEMINI_LLM_MODEL` w pliku `.env`. Oznaczalo to, ze zmiana modelu wymagala edycji pliku i restartu
procesu. Podczas eksperymentowania lub testow roznych modeli bylo to uciazliwe.

## Rozwiazanie

Dodano argument wiersza polecen `--model MODEL` oparty na module `argparse` z biblioteki standardowej.
Argument jest opcjonalny — gdy nie zostanie podany, aplikacja zachowuje sie tak samo jak wczesniej.

### Deklaracja argumentu w `main.py`

```python
parser = argparse.ArgumentParser(
    description="chatbot-app — LangChain + Gemini CLI chatbot"
)
parser.add_argument(
    "--model",
    metavar="MODEL",
    default=None,
    help="Gemini model name to use (overrides GEMINI_LLM_MODEL env var)",
)
args = parser.parse_args()
```

Wartosc `args.model` jest nastepnie przekazywana do funkcji `build_chain`:

```python
conversation_chain, history_state = build_chain(model_override=args.model)
```

## Logika rozwiazywania modelu w `build_chain()`

Funkcja `build_chain` przyjmuje opcjonalny parametr `model_override`. Priorytet jest prosty:
**argument CLI > zmienna srodowiskowa**.

```python
def build_chain(model_override: str | None = None):
    ...
    api_key, env_model = _validate_env()   # czyta GEMINI_LLM_MODEL z .env
    llm_model = model_override or env_model
    if not llm_model:
        console.print(
            "[red]No model specified. Set GEMINI_LLM_MODEL in .env "
            "or pass --model <model-name> on the command line.[/]"
        )
        sys.exit(1)
    llm = ChatGoogleGenerativeAI(model=llm_model, google_api_key=api_key)
```

Jesli ani `model_override`, ani `env_model` nie sa podane, aplikacja wyswietla blad i konczy dzialanie.

## Przyklad uzycia

Uruchomienie z konkretnym modelem:

```bash
python main.py --model gemini-2.0-flash
```

Uruchomienie z modelem z `.env` (stare zachowanie, bez zmian):

```bash
python main.py
```

## Wsteczna zgodnosc

Zmiana jest w pelni wstecznie zgodna. Istniejace pliki `.env` z ustawionym `GEMINI_LLM_MODEL`
dzialaja bez zadnych modyfikacji — `model_override` jest wtedy `None`, wiec `build_chain` siegnie
po wartosc ze zmiennej srodowiskowej, tak jak przed ta zmiana.
