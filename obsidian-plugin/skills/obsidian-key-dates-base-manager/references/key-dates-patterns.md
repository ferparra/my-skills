# Key Dates Base Patterns

Use this file when editing `10 Notes/Key Dates.base`.

## Existing Date-Note Inventory Command

```bash
qmd ls obsidian | awk -F 'qmd://obsidian/' 'NF > 1 { print $2 }' | rg '^00-inbox/[0-9]{4}-[0-9]{2}-[0-9]{2}[.]md$|^periodic/[0-9]{4}/[0-9]{4}-w[0-9]{2}[.]md$|^periodic/[0-9]{4}/[0-9]{4}-[0-9]{2}-monthly-review[.]md$|^periodic/[0-9]{4}/[0-9]{4}[.]md$'
```

## Canonical Date Selection

Use this fallback order:

1. `target_date`
2. `date`
3. `window_start`
4. parsed date from `file.basename` when basename matches `YYYY-MM-DD`

## Path Formula Patterns

```text
inbox_daily_path      = "00 Inbox/YYYY-MM-DD.md"
periodic_daily_path   = "Periodic/YYYY/YYYY-MM-DD.md"
weekly_path           = "Periodic/YYYY/YYYY-WNN.md"
monthly_review_path   = "Periodic/YYYY/YYYY-MM-Monthly-Review.md"
year_path             = "Periodic/YYYY/YYYY.md"
```

## Safe Link Formula Pattern

```text
if(path != "" && file(path), link(path, label), "")
```

## Verification Checklist

1. `obsidian read path="10 Notes/Key Dates.base"`
2. `obsidian links path="10 Notes/Key Dates.base" total`
3. `obsidian unresolved total`
