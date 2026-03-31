# Vault Health Check Reference

## Overview

This document describes the individual health checks performed by the vault health auditor,
their thresholds, and how to interpret results.

## Check: Broken Wiki-Links

**What it detects:** Any `[[wikilink]]` in note body where the target file does not exist.

**Detection method:**
1. Parse all `[[...]]` patterns from note bodies
2. Resolve each link against the vault file index
3. If no matching file exists, flag as broken

**Threshold:** Any broken link is reported.

**Auto-fix:** No — requires manual review or link update.

**Remediation:**
- Delete the broken link
- Create the missing target note
- Fix the link to point to an existing note

## Check: Orphaned Notes

**What it detects:** Notes with zero incoming links and zero outgoing links.

**Detection method:**
1. Count outgoing links per note (wiki-links in body)
2. Count incoming links per note (backlinks from other notes)
3. Notes where both counts are zero are orphaned

**Threshold:** Any note with 0 incoming AND 0 outgoing links.

**Auto-fix:** No — requires understanding of note purpose.

**Remediation:**
- Link the note from relevant context notes
- Add to a daily note or index
- Delete if truly unused

## Check: Low Connection Strength

**What it detects:** Notes where `connection_strength < 2.0`.

**Detection method:**
1. Read `connection_strength` from frontmatter
2. Compare against threshold

**Threshold:** `connection_strength < 2.0`

**Auto-fix:** No — this is a content/graph health signal.

**Remediation:**
- Add more outgoing links to relevant notes
- Add potential_links in frontmatter
- Increase backlink density

## Check: Schema Drift

**What it detects:** Notes with a `*_kind` field whose value is not in the known taxonomy.

**Detection method:**
1. Detect which kind field is present (person_kind, exercise_kind, etc.)
2. Check value against KNOWN_KINDS taxonomy
3. Flag if value not in known set

**Threshold:** Any unknown kind value.

**Auto-fix:** Yes — injects FIXME_review_required tag. Does not change kind value.

**Remediation:**
- Correct the kind value if wrong
- Add new valid kind value to taxonomy if intentional

## Check: Misplaced Notes

**What it detects:** Notes whose path does not match their kind's expected directory.

**Kind-to-directory mapping:**
| Kind field | Expected directory |
|---|---|
| person_kind | People/ |
| exercise_kind | 20 Resources/Exercises/ |
| brokerage_activity_kind | 20 Resources/Investments/Brokerage Activity/ |
| portfolio_holding_kind | 20 Resources/Investments/Portfolio Holdings/ |
| cv_entry_kind | 20 Resources/Career/ |
| zettel_kind | 30 Zettelkasten/ |
| key_date_kind | 20 Resources/Key Dates/ |

**Threshold:** Any note where path does not contain expected directory.

**Auto-fix:** Yes — moves file and updates all incoming wiki-links.

**Remediation:**
- Run fix_issues.py in fix mode
- Or manually move and update links

## Check: Duplicate Zettel IDs

**What it detects:** Multiple notes with the same zettel_id (or id) field.

**Detection method:**
1. Extract zettel_id from frontmatter
2. Group by zettel_id
3. Flag groups with more than one path

**Threshold:** Any duplicate zettel_id.

**Auto-fix:** Yes — keeps note with earliest created date, regenerates IDs for others.

**Remediation:**
- Run fix_issues.py in fix mode
- Or manually deduplicate and regenerate IDs

## Check: Stale Notes

**What it detects:** Notes not modified in >90 days.

**Detection method:**
1. Read file stat (mtime) for each note
2. Compute days since last modification
3. Flag if >90 days

**Threshold:** `days_since_modified > 90`

**Auto-fix:** No — requires manual review.

**Remediation:**
- Update the note with new content
- Archive if no longer relevant
- Delete if truly stale

## Zombies

Notes that are both stale (>180 days) AND have zero incoming links are "zombies."
These are highest priority for review or deletion.
