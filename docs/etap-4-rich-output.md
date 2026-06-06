# Etap 4: Kolorowy output w terminalu (rich)

`last_updated: 2026-06-06`

## Co to jest `rich`

[`rich`](https://pypi.org/project/rich/) to biblioteka Pythona do formatowania outputu
w terminalu. Oferuje kolorowy tekst, style (pogrubienie, kursywa, przyciemnienie), tabele,
paski postepu i wiele wiecej — bez koniecznosci recznie wpisywania kodow ANSI.

## Instancja `Console` na poziomie modulu

W `main.py` tworzony jest jeden wspoldzielony obiekt `Console`:

```python
from rich.console import Console

console = Console()
```

Pojedyncza instancja jest utozywana przez caly program. Dzieki temu ustawienia (np. szerokos
terminala, wykrywanie kolorow) sa spojne.

## Konwencje stylow

Ponizej pelna lista znacznikow stosowanych w aplikacji wraz z ich znaczeniem:

### Monit uzytkownika

```python
console.print("[bold green]You:[/] ", end="")
```

Zielony, pogrubiony napis `You:` odrozniony od odpowiedzi modelu — uzytkownik od razu wie,
ktora czesc ekranu nalezy do niego.

### Etykieta odpowiedzi AI

```python
console.print("[bold cyan]AI:[/] ", end="")
```

Cyjanowy, pogrubiony napis `AI:` wprowadza odpowiedz modelu. Para `You:`/`AI:` tworzy
wizualny rytm przypominajacy interfejsy komunikatorow.

### Ostrzezenia dla uzytkownika

```python
console.print("[yellow]Warning:[/] SYSTEM_PROMPT contains unfilled placeholders: ...")
console.print(f"[yellow]Warning:[/] input exceeds {MAX_INPUT_LENGTH} characters. ...")
```

Zolty kolor sygnalizuje stan, ktory wymaga uwagi, ale nie przerywa dzialania programu.

### Bledy

```python
console.print("[red]Error:[/] API key invalid or quota exceeded.")
console.print("[red]Missing required env var: GEMINI_API_KEY. ...")
```

Czerwony kolor oznacza blad krytyczny lub stan, po ktorym program nie moze kontynuowac.

### Wiadomosci statusowe

```python
console.print(f"[dim]Resumed session with {len(prior_messages)} previous messages.[/]")
console.print("[dim]Session saved.[/]")
```

`[dim]` (przyciemnienie) sluzy do komunikatow pomocniczych, ktore nie sa czescia rozmowy —
sa widoczne, ale nie walcza o uwage z wlasciwym dialogiem.

### Baner powitalny

```python
console.rule("[bold]chatbot-app[/]")
```

`console.rule()` rysuje pozioma linie z centrycznie umieszczonym tekstem. Sluzy jako
wizualny separator miedzy fazas startu a poczatkiem rozmowy.

## Dlaczego strumieniowanie uzywa zwyklego `print()`

Odpowiedz modelu jest wyswietlana strumieniowo (token po tokenie):

```python
for chunk in conversation_chain.stream({"input": user_prompt}, config=config):
    print(chunk, end="", flush=True)
```

`rich` buforuje output i przetwarza znaczniki dopiero przy pelnym wywolaniu `console.print`.
Uzycie `console.print` w petli strumieniujacej powodowaloby migotanie i niepotrzebne
parsowanie znacznikow na kazdym fragmencie. Zwykly `print` z `flush=True` zapewnia
natychmiastowe wyswietlanie bez tych problemow.

## Jak rozszerzyc: renderowanie Markdown

Jesli odpowiedzi modelu zawieraja formatowanie Markdown, mozna je renderowac dzieki wbudowanej
klasie `Markdown` z biblioteki `rich`:

```python
from rich.markdown import Markdown

# zamiast: print(chunk, end="", flush=True) w petli, zebrac caly response, potem:
console.print(Markdown(full_response))
```

Wymaga to zrezygnowania ze strumieniowania na rzecz zebrania pelnej odpowiedzi — to kompromis
miedzy natychmiastowym outputem a ladnym renderowaniem.
