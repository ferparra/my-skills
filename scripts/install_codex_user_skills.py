#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


def default_codex_skills_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser().resolve() / "skills"
    return (Path.home() / ".codex" / "skills").resolve()


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description=(
            "Install Codex user-level skills from this repository's Claude "
            "marketplace plugin layout without touching .skill artifacts."
        )
    )
    parser.add_argument(
        "skills",
        nargs="*",
        help="Optional skill names to install. Installs every marketplace skill by default.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(repo_root),
        help="Path to the my-skills checkout. Defaults to the parent of this script.",
    )
    parser.add_argument(
        "--dest",
        default=str(default_codex_skills_dir()),
        help="Destination Codex skills directory. Defaults to $CODEX_HOME/skills or ~/.codex/skills.",
    )
    parser.add_argument(
        "--mode",
        choices=("symlink", "copy"),
        default="symlink",
        help="Install skills as symlinks or copied directories. Default: symlink.",
    )
    parser.add_argument(
        "--backup-root",
        help=(
            "Directory used to hold replaced skills. Defaults to "
            "<dest-parent>/skill-backups/<timestamp> when needed."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the actions without modifying the destination.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Required metadata file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def discover_marketplace_skills(repo_root: Path) -> dict[str, Path]:
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    marketplace = load_json(marketplace_path)

    discovered: dict[str, Path] = {}
    for plugin in marketplace.get("plugins", []):
        plugin_source = plugin.get("source")
        plugin_name = plugin.get("name", "<unknown-plugin>")
        if not plugin_source:
            raise SystemExit(f"Marketplace entry is missing source: {plugin_name}")

        plugin_root = (repo_root / plugin_source).resolve()
        plugin_config = load_json(plugin_root / ".claude-plugin" / "plugin.json")
        skills_path = plugin_config.get("skills")
        if not skills_path:
            raise SystemExit(f"Plugin is missing skills path: {plugin_name}")

        skill_root = (plugin_root / skills_path).resolve()
        if not skill_root.is_dir():
            raise SystemExit(f"Skill directory not found for {plugin_name}: {skill_root}")

        for child in sorted(skill_root.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue
            if not (child / "SKILL.md").is_file():
                continue
            if child.name in discovered:
                raise SystemExit(
                    f"Duplicate skill name detected in marketplace discovery: {child.name}"
                )
            discovered[child.name] = child

    if not discovered:
        raise SystemExit(
            f"No skill directories were discovered from marketplace metadata in {repo_root}"
        )
    return discovered


def resolve_requested_skills(
    available_skills: dict[str, Path], requested_names: list[str]
) -> list[tuple[str, Path]]:
    if not requested_names:
        return sorted(available_skills.items())

    missing = [name for name in requested_names if name not in available_skills]
    if missing:
        raise SystemExit(
            "Unknown skill name(s): "
            + ", ".join(missing)
            + "\nAvailable skills: "
            + ", ".join(sorted(available_skills))
        )

    return [(name, available_skills[name]) for name in requested_names]


def default_backup_root(dest_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return dest_dir.parent / "skill-backups" / timestamp


def same_symlink_target(dest: Path, source: Path) -> bool:
    if not dest.is_symlink():
        return False
    return dest.resolve(strict=False) == source.resolve()


def install_skill(
    name: str,
    source: Path,
    dest_dir: Path,
    mode: str,
    backup_root: Path,
    dry_run: bool,
) -> tuple[str, Path | None]:
    dest = dest_dir / name
    backup_path: Path | None = None

    if same_symlink_target(dest, source):
        return "unchanged", None

    if dest.exists() or dest.is_symlink():
        backup_path = backup_root / name
        if backup_path.exists() or backup_path.is_symlink():
            raise SystemExit(f"Backup path already exists: {backup_path}")
        if not dry_run:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            dest.rename(backup_path)

    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
        if mode == "symlink":
            dest.symlink_to(source)
        else:
            shutil.copytree(source, dest)

    if backup_path is not None:
        return "replaced", backup_path
    return "installed", None


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).expanduser().resolve()
    dest_dir = Path(args.dest).expanduser().resolve()

    if not repo_root.is_dir():
        raise SystemExit(f"Repo root not found: {repo_root}")

    available_skills = discover_marketplace_skills(repo_root)
    selected_skills = resolve_requested_skills(available_skills, args.skills)
    backup_root = (
        Path(args.backup_root).expanduser().resolve()
        if args.backup_root
        else default_backup_root(dest_dir)
    )

    print(f"Repo root: {repo_root}")
    print(f"Destination: {dest_dir}")
    print(f"Mode: {args.mode}")
    print(f"Discovered skills: {len(available_skills)}")
    if args.dry_run:
        print("Dry run: yes")

    replaced_any = False
    for name, source in selected_skills:
        status, backup_path = install_skill(
            name=name,
            source=source,
            dest_dir=dest_dir,
            mode=args.mode,
            backup_root=backup_root,
            dry_run=args.dry_run,
        )

        if status == "unchanged":
            print(f"UNCHANGED {name} -> {dest_dir / name}")
            continue

        if status == "replaced":
            replaced_any = True
            print(f"REPLACED {name} -> {dest_dir / name} (backup: {backup_path})")
            continue

        print(f"INSTALLED {name} -> {dest_dir / name}")

    if replaced_any:
        print(f"Backups: {backup_root}")
    print("Marketplace .skill artifacts were not modified.")
    if not args.dry_run:
        print("Restart Codex to pick up new skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
