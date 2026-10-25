# Trigger the Security note only for increased exposure

## Problem

The user reports a Security note for a new model call in an existing LLM
assessment tool. The call rewrites finding texts that upstream models already
write from repository content, goes to a model host that already receives
finding titles, and its failure mode is covered by code that keeps severity,
locations, and IDs. The note still appeared, described those controls, and
cited the user's acceptance.

Three triggers in the core allow this. The Security note condition names no
reference point for "creates or worsens", so a new call is compared with no
call instead of with the existing data flow. "Changed critical boundaries with
unverified dangerous failures" lost the "concrete" and "materially" of its
source requirement in a reduction meant to keep behavior. The accepted-risk
record in Operating Mode checks only materiality, not whether the delivery
creates or worsens the risk.

## Goal

Trigger the Security note only when the delivery, after effective controls,
allows an outcome or a data receipt the affected data flow did not already
allow. Source: the user's request on 2026-10-25 that the note be emitted only
where it is really relevant, and approval of the proposed wording in this
conversation. Record NOTE-003 to NOTE-005 here and add a model case modeled on
the reported note.

## Non-goals

No change to the note's form, the main-answer reporting threshold, the
confirmation duty, version, release, installation, loader, or modules. Material
risks the delivery does create or worsen keep their note.

## Compatibility

A delivery that newly lets an attacker reach an outcome or a party receive a
class of data still produces one note. A new component, call, or injection
point that adds no such outcome, and an accepted risk the delivery does not
create or worsen, produce none. Changed critical boundaries trigger the note
only for a concrete dangerous failure that remains materially unverified.
