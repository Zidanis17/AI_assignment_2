% CSEN901 - Assignment 2: chess planning using situation calculus.
%
% Team members:
% 1. Islam Mohamed Zeidan | ID: 58-18214 | Tutorial: 7
% 2. Mahmoud Hatem | ID: 58-6860 | Tutorial: 7

% Keep this file beside the KB. Change ONLY this line to switch to KB2.pl.
:- include('KB1.pl').

/*
   ONE FLUENT: board(Knights, Bishops, Situation)

   Knights and Bishops are sorted lists of coordinate pairs (X,Y).
   Situation is s0 or result(Action, PreviousSituation).
   board(Knights, Bishops, Situation) means that these are ALL the knights
   and bishops present after the actions described by Situation.

   Keeping both lists in one fluent makes the choice of moving piece shared
   by the entire board. Actions name only a destination, so several pieces
   may be able to perform the same action; each choice gives a separate,
   internally consistent successor board. Exactly one piece moves.

   All other predicates below are static geometry, list operations, or search
   helpers. No other predicate is used as a fluent, and the KB is never mutated.
*/

% Initial-state axiom: the supplied KB describes precisely the board at s0.
board(Knights, Bishops, s0) :-
    findall((X,Y), knight_at(X,Y), InitialKnights),
    findall((X,Y), bishop_at(X,Y), InitialBishops),
    sort(InitialKnights, Knights),
    sort(InitialBishops, Bishops).

% SUCCESSOR-STATE AXIOM:
% A board holds in result(Action, Previous) iff a board holds in Previous
% and Action legally transforms that board into this one. legal_move/5
% specifies both the action's effect and the persistence of all other pieces.
% This recursion also rejects a history containing ANY illegal earlier action.
board(Knights, Bishops, result(Action, Previous)) :-
    board(OldKnights, OldBishops, Previous),
    legal_move(Action, OldKnights, OldBishops, Knights, Bishops).

% A knight action changes just one member of the knight list.
% The bishop list and every unselected knight persist unchanged.
legal_move(k(X,Y), OldKnights, Bishops, Knights, Bishops) :-
    select(From, OldKnights, OtherKnights),
    knight_destination(From, (X,Y)),
    empty_cell((X,Y), OldKnights, Bishops),
    sort([(X,Y)|OtherKnights], Knights).

% A bishop action changes just one member of the bishop list.
% The knight list and every unselected bishop persist unchanged.
% Intermediate cells are deliberately not checked: bishops may pass pieces.
legal_move(b(X,Y), Knights, OldBishops, Knights, Bishops) :-
    select(From, OldBishops, OtherBishops),
    bishop_destination(From, (X,Y)),
    empty_cell((X,Y), Knights, OldBishops),
    sort([(X,Y)|OtherBishops], Bishops).

% Negation is applied only after the destination and both lists are ground.
empty_cell(Cell, Knights, Bishops) :-
    \+ memberchk(Cell, Knights),
    \+ memberchk(Cell, Bishops).

% Coordinates may be supplied or generated. Non-integer/out-of-range supplied
% coordinates fail rather than raising an arithmetic/type exception.
cell((X,Y)) :-
    grid(Width, Height),
    coordinate(X, Width),
    coordinate(Y, Height).

coordinate(Value, Maximum) :-
    (   var(Value)
    ->  between(1, Maximum, Value)
    ;   integer(Value), Value >= 1, Value =< Maximum
    ).

% The eight legal knight displacements.
knight_delta( 2, 1).
knight_delta( 2,-1).
knight_delta(-2, 1).
knight_delta(-2,-1).
knight_delta( 1, 2).
knight_delta( 1,-2).
knight_delta(-1, 2).
knight_delta(-1,-2).

knight_destination((FromX,FromY), (X,Y)) :-
    knight_delta(DX, DY),
    X is FromX + DX,
    Y is FromY + DY,
    cell((X,Y)).

bishop_direction( 1, 1).
bishop_direction( 1,-1).
bishop_direction(-1, 1).
bishop_direction(-1,-1).

% Enumerate nonzero distances along each diagonal, stopping at the board edge.
bishop_destination((FromX,FromY), (X,Y)) :-
    grid(Width, Height),
    bishop_direction(DX, DY),
    distance_to_edge(FromX, Width, DX, HorizontalLimit),
    distance_to_edge(FromY, Height, DY, VerticalLimit),
    Maximum is min(HorizontalLimit, VerticalLimit),
    between(1, Maximum, Distance),
    X is FromX + DX * Distance,
    Y is FromY + DY * Distance.

distance_to_edge(Position, Maximum, 1, Distance) :-
    Distance is Maximum - Position.
distance_to_edge(Position, _, -1, Distance) :-
    Distance is Position - 1.

/*
   goal(+KnightCell, +BishopCell, ?Situation)

   With a ground Situation, validate exactly that supplied history. Legal
   histories containing repeated boards are accepted in this mode.

   Otherwise, perform iterative deepening in the NUMBER OF ACTIONS, rather
   than Prolog's implementation-dependent call depth. Each expansion reasons
   through the successor-state axiom above. Along a search path, do not revisit
   a board: a shortest route to any reachable board never needs such a cycle.

   A target denotes SOME knight and SOME bishop, not a particular piece ID.
   Variable coordinates can also be enumerated over the finite board.
*/
goal(KnightCell, BishopCell, Situation) :-
    cell(KnightCell),
    cell(BishopCell),
    KnightCell \= BishopCell,
    acyclic_term(Situation),
    bishop_target_possible(BishopCell),
    knight_target_possible(KnightCell),
    (   ground(Situation)
    ->  once((board(Knights, Bishops, Situation),
              memberchk(KnightCell, Knights),
              memberchk(BishopCell, Bishops)))
    ;   board(InitialKnights, InitialBishops, s0),
        Initial = node(s0, InitialKnights, InitialBishops),
        Seen = [positions(InitialKnights, InitialBishops)],
        iterative_plan(0, Initial, Seen, KnightCell, BishopCell, Situation)
    ).

% Static impossibility checks: bishops preserve square colour. On a board
% only one cell wide/high they cannot move at all. Occupancy may impose more
% restrictions; these checks never reject a genuinely reachable target.
bishop_target_possible((X,Y)) :-
    once((bishop_at(FromX,FromY),
          (   X =:= FromX, Y =:= FromY
          ;   grid(Width, Height), Width > 1, Height > 1,
              (X + Y) mod 2 =:= (FromX + FromY) mod 2
          ))).

% Ignore occupancy and find the knight's static connected component. This
% catches unreachable targets on narrow/tiny boards before attempting plans.
% This helper describes fixed board geometry, not a situation-dependent fact.
knight_target_possible(Target) :-
    findall((X,Y), knight_at(X,Y), Starts),
    sort(Starts, InitialCells),
    knight_reachable(InitialCells, InitialCells, Target).

knight_reachable([Cell|Rest], Seen, Target) :-
    (   Cell == Target
    ->  true
    ;   findall(Next,
                (knight_destination(Cell, Next), \+ memberchk(Next, Seen)),
                NewCells),
        append(Rest, NewCells, Queue),
        append(NewCells, Seen, NewSeen),
        knight_reachable(Queue, NewSeen, Target)
    ).

iterative_plan(Depth, Initial, Seen, KnightCell, BishopCell, Situation) :-
    (   plan_at_depth(Depth, Initial, Seen,
                      KnightCell, BishopCell, Situation)
    ;   NextDepth is Depth + 1,
        % Deepen only if a longer simple path actually exists. If not, the
        % finite reachable search space is exhausted, so fail instead of loop.
        once(bounded_path(NextDepth, Initial, Seen, _, _)),
        iterative_plan(NextDepth, Initial, Seen,
                       KnightCell, BishopCell, Situation)
    ).

plan_at_depth(0, node(Situation, Knights, Bishops), _,
              KnightCell, BishopCell, Situation) :-
    memberchk(KnightCell, Knights),
    memberchk(BishopCell, Bishops).
plan_at_depth(Depth, Initial, Seen, KnightCell, BishopCell, Situation) :-
    Depth > 0,
    % In a minimal solution the final move must put a piece on one of the
    % requested squares. This safe search restriction avoids many useless
    % final moves. Validation of supplied histories has no such restriction.
    target_action(KnightCell, BishopCell, LastAction),
    bounded_path(Depth, Initial, Seen, LastAction,
                 node(Situation, Knights, Bishops)),
    memberchk(KnightCell, Knights),
    memberchk(BishopCell, Bishops).

target_action((X,Y), _, k(X,Y)).
target_action(_, (X,Y), b(X,Y)).

% node(Situation, Knights, Bishops) is a search record, not another fluent.
% Canonical sorted position lists let Seen compare complete board layouts.
bounded_path(0, Node, _, _, Node).
bounded_path(Remaining, node(Previous,OldKnights,OldBishops), Seen,
             LastAction, FinalNode) :-
    Remaining > 0,
    (Remaining =:= 1 -> Action = LastAction ; true),
    Next = result(Action, Previous),
    board(Knights, Bishops, Next),
    % A destination-only history can have several possible previous boards.
    % Keep the successor consistent with this search branch's chosen board.
    once(legal_move(Action, OldKnights, OldBishops, Knights, Bishops)),
    Positions = positions(Knights, Bishops),
    \+ memberchk(Positions, Seen),
    Rest is Remaining - 1,
    bounded_path(Rest, node(Next, Knights, Bishops), [Positions|Seen],
                 LastAction, FinalNode).
