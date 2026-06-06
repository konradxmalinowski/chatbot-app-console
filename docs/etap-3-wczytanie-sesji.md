# Etap 3: Wczytywanie poprzedniej sesji przy starcie

`last_updated: 2026-06-06`

## Cel

Sam zapis historii (Etap 2) nie daje ciaglej rozmowy — konieczne jest rowniez jej odczytanie
przy kazdym uruchomieniu programu. Ten etap uzupelnia mechanizm o strone wczytujaca.

## Jak dziala wczytywanie w `build_chain()`

Zaraz po zbudowaniu lancucha LangChain, jeszcze przed wejsciem w petle czatu, `build_chain`
wywoluje `load_session`. Jesli plik sesji istnieje i nie jest uszkodzony, zwrocone wiadomosci
sa wstrzykiwane do `InMemoryChatMessageHistory` przez metode `add_messages`:

```python
prior_messages = load_session(DEFAULT_SESSION_ID, SESSIONS_DIR)
if prior_messages:
    restored = InMemoryChatMessageHistory()
    restored.add_messages(prior_messages)
    history_state[DEFAULT_SESSION_ID] = restored
    console.print(
        f"[dim]Resumed session with {len(prior_messages)} previous messages.[/]"
    )
```

Obiekt `restored` jest od razu umieszczany w slowniku `history_state` pod kluczem `DEFAULT_SESSION_ID`
(`"1"`). Gdy petla czatu wyslze pierwsze zapytanie, `RunnableWithMessageHistory` znajdzie juz
gotowa, zasilona historia — model widzi poprzednie wiadomosci tak, jakby rozmowa nigdy
nie zostala przerwana.

## Dlaczego `add_messages`, a nie puste pole `messages`

`InMemoryChatMessageHistory` nie przyjmuje wiadomosci w konstruktorze. Metoda `add_messages`
to oficjalny sposob hurtowego zasilenia historii lista obiektow `BaseMessage`. Jest to operacja
jednorazowa przy starcie — potem LangChain dopisuje kolejne wiadomosci automatycznie.

## Komunikat widoczny dla uzytkownika

Jesli sesja zostala wczytana poprawnie, uzytkownik widzi:

```
Resumed session with 4 previous messages.
```

Liczba oznacza laczna liczbe wiadomosci (wliczajac zarowno strony `human`, jak i `ai`).
Gdy nie ma zapisanej sesji (pierwsze uruchomienie), komunikat nie jest wyswietlany.

## Ciagloc miedzy restartami — schemat pelnego cyklu

```
Uruchomienie 1:
  build_chain() → load_session() → [] (brak pliku)
  petle czatu → 3 wymiany → save_session() → sessions/1.json

Uruchomienie 2:
  build_chain() → load_session() → [6 wiadomosci]
  add_messages() → historia zasilona
  petle czatu → nowe wymiany dolaczone → save_session() → plik nadpisany
```

Dzieki temu kazde kolejne uruchomienie kontynuuje rozmowe zamiast ja zaczynac od nowa,
bez potrzeby przechowywania stanu po stronie uzytkownika.
