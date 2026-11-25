"""Run the sample queries and compare tiny boards with an independent oracle.

Run from the workspace root with: python tests/run_tests.py
Each suite gets a temporary copy of the solution and its own KB. The original
solution, selected include directive, and supplied KBs are never modified.
"""

from collections import deque
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "Assignment_2" / "Assignment 2 KBs"
SOLUTIONS = sorted(KB_DIR.glob("chess_*.pl"))
if len(SOLUTIONS) != 1:
    raise SystemExit("Expected exactly one chess_*.pl solution beside the KBs.")
SOLUTION = SOLUTIONS[0]
SWIPL = shutil.which("swipl")
if not SWIPL:
    candidate = Path(r"C:\Program Files\swipl\bin\swipl.exe")
    if candidate.is_file():
        SWIPL = str(candidate)
if not SWIPL:
    raise SystemExit("SWI-Prolog was not found. Install it or add swipl to PATH.")


def read_board(facts):
    width, height = map(int, re.search(r"grid\((\d+),\s*(\d+)\)", facts).groups())
    pieces = []
    for kind in ("knight", "bishop"):
        pieces.append(frozenset(
            (int(x), int(y))
            for x, y in re.findall(rf"{kind}_at\((\d+),\s*(\d+)\)", facts)
        ))
    return width, height, tuple(pieces)


def destinations(kind, origin, width, height):
    """Independent geometric oracle: test every square using displacements."""
    for x in range(1, width + 1):
        for y in range(1, height + 1):
            dx, dy = abs(x - origin[0]), abs(y - origin[1])
            if kind == "k" and sorted((dx, dy)) == [1, 2]:
                yield x, y
            elif kind == "b" and dx == dy and dx > 0:
                yield x, y


def successors(state, width, height, action=None):
    occupied = state[0] | state[1]
    for index, kind in enumerate(("k", "b")):
        if action and action[0] != kind:
            continue
        for origin in state[index]:
            for target in destinations(kind, origin, width, height):
                if target in occupied or (action and target != tuple(action[1:])):
                    continue
                changed = frozenset((state[index] - {origin}) | {target})
                yield (changed, state[1]) if index == 0 else (state[0], changed)


def reachable_states(initial, width, height):
    queue = deque([initial])
    seen = {initial}
    while queue:
        for successor in successors(queue.popleft(), width, height):
            if successor not in seen:
                seen.add(successor)
                queue.append(successor)
    return seen


def replay_plan(plan, facts):
    """Replay ALL possible source choices, since actions specify no source."""
    width, height, initial = read_board(facts)
    possible = {initial}
    for index, action in enumerate(plan["actions"], 1):
        possible = {
            new for state in possible
            for new in successors(state, width, height, action)
        }
        if not possible:
            raise AssertionError(f"Illegal action {index}: {action}; plan={plan}")
        for knights, bishops in possible:
            assert len(knights) == len(initial[0]), "A knight disappeared"
            assert len(bishops) == len(initial[1]), "A bishop disappeared"
            assert not knights & bishops, "Two pieces share a square"
    knight, bishop = tuple(plan["knight"]), tuple(plan["bishop"])
    assert any(knight in k and bishop in b for k, b in possible), plan


def test(name, query, succeeds=True):
    options = "[nondet]" if succeeds else "[fail]"
    return f"test({name}, {options}) :- call_with_time_limit(15, ({query}))."


def oracle_tests(facts):
    width, height, initial = read_board(facts)
    states = reachable_states(initial, width, height)
    cells = [(x, y) for x in range(1, width + 1) for y in range(1, height + 1)]
    tests = []
    for knight in cells:
        for bishop in cells:
            expected = any(knight in k and bishop in b for k, b in states)
            query = f"once(goal({pair(knight)},{pair(bishop)},_))"
            name = f"oracle_k{knight[0]}_{knight[1]}_b{bishop[0]}_{bishop[1]}"
            tests.append(test(name, query, expected))
    return tests


def pair(cell):
    return f"({cell[0]},{cell[1]})"


def run_suite(name, facts, cases, targets=()):
    prolog_helpers = r"""
:- use_module(library(http/json)).
plan_actions(s0, []).
plan_actions(result(Action, Previous), Actions) :-
    plan_actions(Previous, Before),
    Action =.. [Kind,X,Y],
    append(Before, [[Kind,X,Y]], Actions).
emit_plan(KX, KY, BX, BY) :-
    call_with_time_limit(15, once(goal((KX,KY), (BX,BY), Situation))),
    plan_actions(Situation, Actions),
    json_write_dict(current_output,
                    _{knight:[KX,KY], bishop:[BX,BY], actions:Actions},
                    [width(0)]),
    nl.
"""
    emissions = [f"emit_plan({kx},{ky},{bx},{by})" for (kx, ky), (bx, by) in targets]
    main = ", ".join(["run_tests"] + emissions)
    suite = (":- use_module(library(plunit)).\n"
             ":- begin_tests(chess).\n" + "\n".join(cases)
             + "\n:- end_tests(chess).\n" + prolog_helpers
             + f"\nmain :- {main}.\n")
    with tempfile.TemporaryDirectory(prefix="chess-tests-") as temporary:
        directory = Path(temporary)
        # Both real KBs are loaded under the include filename selected by the
        # implementation, just as a grader can supply its own KB facts.
        source = SOLUTION.read_text(encoding="utf-8")
        include = re.search(r"(?m)^:- include\('([^']+)'\)\.", source)
        if include is None:
            raise AssertionError("The solution must include its external KB")
        (directory / include.group(1)).write_text(facts, encoding="utf-8")
        (directory / "chess.pl").write_text(source, encoding="utf-8")
        (directory / "suite.pl").write_text(suite, encoding="utf-8")
        result = subprocess.run(
            [SWIPL, "-q", "-s", "chess.pl", "-s", "suite.pl", "-g", "main", "-t", "halt"],
            cwd=directory, capture_output=True, text=True, timeout=90,
        )
    if result.returncode:
        raise AssertionError(f"{name} failed:\n{result.stdout}\n{result.stderr}")
    plans = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    assert len(plans) == len(targets), (name, result.stdout, result.stderr)
    for plan in plans:
        replay_plan(plan, facts)
    print(f"PASS {name}: {len(cases)} checks, {len(plans)} independently replayed plans")
    return len(cases), len(plans)


def main():
    kb1 = (KB_DIR / "KB1.pl").read_text(encoding="utf-8")
    kb2 = (KB_DIR / "KB2.pl").read_text(encoding="utf-8")
    kb1_cases = [
        test("sample_1_generate", "once(goal((4,3),(2,2),_))"),
        test("sample_2_generate", "once(goal((3,4),(5,4),_))"),
        test("sample_1_provided_plan", "goal((4,3),(2,2),result(k(4,3),result(b(2,2),s0)))"),
        test("sample_2_provided_plan", "goal((3,4),(5,4),result(k(3,4),result(k(2,2),result(k(1,4),result(b(5,4),s0)))))"),
        test("sample_3", "goal((3,4),(4,4),result(k(3,4),result(k(4,2),result(k(2,1),result(b(4,4),s0)))))"),
        test("sample_4", "goal((4,3),(2,2),result(k(4,3),result(k(2,1),result(b(2,2),s0))))"),
        test("sample_5", "goal((4,3),(2,2),result(k(4,3),result(b(1,2),s0)))", False),
        test("sample_6", "goal((4,3),(2,2),result(k(2,5),result(b(2,2),s0)))", False),
        test("initial_goal", "goal((3,3),(1,1),S), S == s0"),
        test("initial_full_board", "board(K,B,s0), K == [(3,3),(5,1)], B == [(1,1),(3,2),(4,6)]"),
        test("same_cell", "goal((3,3),(3,3),_)", False),
        test("outside_width", "goal((7,3),(1,1),_)", False),
        test("outside_height", "goal((3,7),(1,1),_)", False),
        test("zero_coordinate", "goal((0,3),(1,1),_)", False),
        test("noninteger_target", "goal((3.5,3),(1,1),_)", False),
        test("other_bishop_colour", "once(goal((3,3),(1,2),_))"),
        test("knight_diagonal", "goal((4,4),(1,1),result(k(4,4),s0))", False),
        test("knight_capture", "goal((3,2),(1,1),result(k(3,2),s0))", False),
        test("bishop_capture", "goal((5,1),(3,3),result(b(3,3),s0))", False),
        test("bishop_noop", "goal((3,3),(1,1),result(b(1,1),s0))", False),
        test("bad_earlier_move", "goal((3,3),(1,1),result(k(99,99),s0))", False),
        test("unknown_action", "goal((3,3),(1,1),result(wrong,s0))", False),
        test("invalid_history", "goal((3,3),(1,1),wrong)", False),
        test("cyclic_history", "S = result(k(1,2),S), goal((3,3),(1,1),S)", False),
        test("legal_repeated_board", "goal((3,3),(1,1),result(k(3,3),result(k(1,2),s0)))"),
        test("bishop_persists_after_knight", "board(K,B,result(k(1,2),result(b(2,2),s0))), K == [(1,2),(5,1)], B == [(2,2),(3,2),(4,6)]"),
        test("partial_history", "goal((4,3),(1,1),result(k(4,3),Previous)), Previous == s0"),
    ]
    kb2_cases = [
        test("sample_1_generate", "once(goal((6,1),(3,3),_))"),
        test("sample_2_generate", "once(goal((4,1),(3,2),_))"),
        test("sample_3_generate", "once(goal((6,1),(3,2),_))"),
        test("sample_1_provided_plan", "goal((6,1),(3,3),result(k(6,1),result(k(5,3),result(b(3,3),result(k(1,2),s0)))))"),
        test("sample_2_provided_plan", "goal((4,1),(3,2),result(k(4,1),result(b(3,2),s0)))"),
        test("sample_3_provided_plan", "goal((6,1),(3,2),result(k(6,1),result(k(5,3),result(b(3,2),s0))))"),
        test("sample_4", "goal((3,3),(3,3),_)", False),
        test("sample_5", "goal((6,1),(3,3),result(k(2,1),result(k(4,2),result(b(3,3),result(k(2,1),s0)))))", False),
        test("rectangular_bound", "goal((6,6),(1,1),_)", False),
        test("rectangular_corner", "goal((6,5),(1,1),s0)"),
    ]
    ambiguity = "grid(5,5).\nknight_at(1,1).\nknight_at(1,5).\nbishop_at(3,3).\n"
    jumping = "grid(5,5).\nknight_at(3,3).\nbishop_at(1,1).\nbishop_at(2,2).\n"
    full = "grid(3,2).\nknight_at(1,1).\nknight_at(1,2).\nknight_at(2,1).\nknight_at(2,2).\nbishop_at(3,1).\nbishop_at(3,2).\n"
    narrow = "grid(1,4).\nknight_at(1,4).\nbishop_at(1,1).\n"
    tiny1 = "grid(2,2).\nknight_at(1,1).\nbishop_at(1,2).\n"
    tiny2 = "grid(3,2).\nknight_at(1,1).\nbishop_at(3,2).\n"
    suites = [
        ("KB1", kb1, kb1_cases, [((4,3),(2,2)), ((3,4),(5,4))]),
        ("KB2", kb2, kb2_cases, [((6,1),(3,3)), ((4,1),(3,2)), ((6,1),(3,2))]),
        ("ambiguous source", ambiguity, [
            test("both_source_choices", "setof(K,board(K,[(3,3)],result(k(2,3),s0)),Boards), Boards == [[(1,1),(2,3)],[(1,5),(2,3)]]"),
            test("only_one_knight_moves", "forall(board(K,_,result(k(2,3),s0)),length(K,2))"),
            test("vacated_source_usable", "goal((1,5),(1,1),result(b(1,1),result(k(2,3),s0)))"),
            test("occupied_source_unusable", "goal((1,5),(1,1),result(b(1,1),s0))", False),
        ], [((1,5),(1,1))]),
        ("bishop jumping", jumping, [
            test("jump_both_piece_types", "goal((3,3),(5,5),result(b(5,5),s0))"),
            test("blockers_persist", "board(K,B,result(b(5,5),s0)), K == [(3,3)], B == [(2,2),(5,5)]"),
            test("bishop_same_type_capture", "goal((3,3),(2,2),result(b(2,2),s0))", False),
            test("wrong_bishop_colour", "goal((3,3),(1,2),_)", False),
        ], [((3,3),(5,5))]),
        ("full board", full, [
            test("initial", "goal((1,1),(3,2),s0)"),
            test("no_free_destination", "goal((3,1),(1,1),_)", False),
        ], []),
        ("narrow board", narrow, [
            test("stationary_bishop", "goal((1,4),(1,3),_)", False),
            test("stationary_knight", "goal((1,2),(1,1),_)", False),
            test("initial", "goal((1,4),(1,1),s0)"),
        ], []),
        ("2x2 exhaustive oracle", tiny1, oracle_tests(tiny1), []),
        ("3x2 exhaustive oracle", tiny2, oracle_tests(tiny2), [((3,2),(1,2))]),
    ]
    total_tests = total_plans = 0
    for arguments in suites:
        count, plans = run_suite(*arguments)
        total_tests += count
        total_plans += plans
    print(f"\nAll {total_tests} checks passed; {total_plans} generated plans independently replayed.")


if __name__ == "__main__":
    main()
