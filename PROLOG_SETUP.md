# Running Prolog

SWI-Prolog 10.0.2 and the VSC-Prolog extension are installed.

## In VS Code

1. Open this `Assignment_2` workspace folder in VS Code.
2. Open `Assignment_2/Assignment 2 KBs/chess_58-18214.pl`.
3. Press **Ctrl+Shift+B** to load the active file into an interactive Prolog terminal.
4. At the `?-` prompt, enter a query such as `grid(W, H).`.

The task uses the installed interpreter directly, so it also works in an editor
that was already open before installation. Save a file before running it.

## In PowerShell

From this workspace root:

```powershell
swipl -s '.\Assignment_2\Assignment 2 KBs\chess_58-18214.pl'
```

If an existing terminal does not recognize `swipl`, open a new terminal. You can
also use the full path immediately:

```powershell
& 'C:\Program Files\swipl\bin\swipl.exe' -s '.\Assignment_2\Assignment 2 KBs\chess_58-18214.pl'
```

## First queries

Enter these at the Prolog prompt, without typing the `?-` prompt itself:

```prolog
grid(W, H).
knight_at(X, Y).
bishop_at(X, Y).
```

Find a plan that leaves some knight at `(4,3)` and some bishop at `(2,2)`:

```prolog
goal((4,3), (2,2), S).
```

One valid KB1 answer is:

```prolog
S = result(k(4,3), result(b(2,2), s0)).
```

Read from the inside out: move the bishop first, then the knight. Other valid
plans can also be returned. To check this exact history instead of searching:

```prolog
goal((4,3), (2,2), result(k(4,3), result(b(2,2), s0))).
```

End every query with a period and press Enter. If Prolog offers additional
answers, press `;` for the next answer or Enter to stop asking for more.

After editing and saving a loaded file, reload it with:

```prolog
make.
```

Exit back to PowerShell with:

```prolog
halt.
```

The implementation currently loads KB1. Change its include directive to `KB2.pl` to use
the second board, then restart the Prolog session. Load only one KB at a time.

## How the solution works

The implementation uses **one fluent**, `board(Knights, Bishops, Situation)`.
The two lists describe all pieces in that situation. Coordinates in each list
are sorted so identical layouts have identical representations.

The initial-state axiom reads the external KB at `s0`. The successor-state axiom
defines the board at `result(Action, Previous)` using the board at `Previous`
and a legal move. A move replaces exactly one source square with its destination;
all other pieces persist. Moving a knight preserves the entire bishop list,
and moving a bishop preserves the entire knight list.

Using a single fluent is useful because `k(X,Y)` and `b(X,Y)` name only a
destination. When several pieces can move there, Prolog explores those source
choices as separate complete boards. It does not remove all possible sources
or combine positions from incompatible source choices.

`goal/3` has two modes:

- A fully supplied situation is checked by the fluent and successor-state axiom.
  Illegal moves anywhere in the history cause failure. Legal cycles are allowed.
- A variable situation is found by iterative deepening over action counts.
  Every search expansion uses the fluent. Search records retain consistent
  predecessor choices, and repeated layouts on the same path are pruned.

The planner checks board bounds, distinct target squares, bishop square colour,
and empty-board knight reachability before searching. These are necessary
conditions; successful plans must still respect every actual occupied square.
Bishop intermediate squares are ignored, as required by the assignment.

Search stops deepening when no longer simple path exists. The board state space
is finite, so impossible targets eventually fail. Exhaustive search can still
take substantial time on larger boards or difficult impossible configurations.
The final-action search shortcut seeks plans ending on a requested square;
validation accepts any legal supplied history that satisfies the goal.

## Automated checks

From the workspace root, run:

```powershell
python tests/run_tests.py
```

The suite runs 102 checks covering both public KBs and queries, legal and
illegal histories, piece preservation, multiple possible movers, bishop jumps,
rectangular/narrow/full boards, and all target pairs on two tiny boards. Those
tiny-board answers are compared with an independent Python breadth-first search.
Eight generated plans are also replayed by an independent move simulator.

Tests use temporary KBs and copies of the solution. They do not change the
selected include directive or the supplied project files, and are not part of
the submission. No additional Python packages are required.

## Submission

Submit only `chess_58-18214.pl`. Keep the KB facts external. The header includes
Islam Mohamed Zeidan, ID 58-18214, tutorial 7, and Mahmoud Hatem's name.
Mahmoud's ID and tutorial remain marked `TODO` until they are supplied.

References: [SWI-Prolog quick start](https://www.swi-prolog.org/man/quickstart.html)
and [VSC-Prolog](https://github.com/arthwang/vsc-prolog).
