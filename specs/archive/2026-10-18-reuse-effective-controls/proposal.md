# Scope application controls and reuse effective protection

## Problem

A reported assistant response attributed filename sanitization and display
truncation to the baseline without explaining the uncovered path or resource
consumption. The excerpt does not establish whether those measures were redundant.
Existing guidance to use established controls leaves that distinction implicit.
Broad application controls can also intrude into standalone cloud and operations
tasks that the user does not want this application-development baseline to govern.

## Goal

Make assistants trace affected paths through existing controls before adding
protection, and apply resource limits at the operation consuming the resource.
Source: the user's approval of the proposed OM-001 and LIMITS-001 wording on
2026-10-18, followed by the request to implement and commit it.
The user subsequently approved an application-development scope and explicitly
excluded standalone cloud and operations work, including AWS, IAM and Terraform.

## Non-goals

No attribution, version, release, or permission changes. No blanket
exemption for terminal output, no requirement for an exploit demonstration, and
no application-specific controls in the baseline. Do not change ERRORS-001.

## Compatibility

Existing effective controls must be reused without duplication; newly uncovered
paths still require protection. Application controls apply to application-development
and review tasks, including build and deployment configuration within those tasks;
standalone operations and documentation do not trigger them. Assistant safeguards
remain applicable throughout. Update the requirement catalog, existing scoped-change
and untrusted-input checks, and routing coverage for standalone operations.
