#!/usr/bin/env bash
# Bundle every git repo under ~/dev into a single verifiable file each.
#
# Why bundles and not a folder upload: .git is Hidden on Windows, and cloud
# clients routinely skip hidden directories. A folder upload that silently
# drops .git looks successful and loses all history and every unpushed commit.
# A bundle is one ordinary file holding the full history, and it verifies.
#
# Usage:   bash scripts/backup_repos.sh [outdir]
# Default outdir: ~/repo-bundles
#
# Restore: git clone <repo>.bundle <repo>

set -uo pipefail

DEV="${DEV:-$HOME/dev}"
OUT="${1:-$HOME/repo-bundles}"
mkdir -p "$OUT"

echo "Bundling repos from $DEV -> $OUT"
echo

fail=0
for d in "$DEV"/*/; do
    name=$(basename "$d")
    [ -d "$d/.git" ] || continue

    dirty=$(git -C "$d" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    if [ "$dirty" != "0" ]; then
        # ponytail: uncommitted work is not in any commit, so --all cannot see it.
        # Snapshot it as a patch beside the bundle rather than committing on the
        # user's behalf.
        git -C "$d" diff HEAD > "$OUT/$name.dirty.patch" 2>/dev/null
        git -C "$d" status --porcelain > "$OUT/$name.untracked.txt" 2>/dev/null
        echo "  ! $name has $dirty dirty paths -> $name.dirty.patch (tracked changes only)"
    fi

    if git -C "$d" bundle create "$OUT/$name.bundle" --all >/dev/null 2>&1; then
        sz=$(du -h "$OUT/$name.bundle" | cut -f1)
        printf "  ok %-28s %s\n" "$name" "$sz"
    else
        echo "  FAIL $name (empty repo? no commits?)"
        fail=1
    fi
done

echo
echo "Archiving untracked files..."
# ponytail: tar, not commit. Untracked sets are mostly caches and build
# artifacts, and at least one repo has an untracked env.env with a GitHub
# remote - committing would push burned credentials and bloat history forever.
# A tarball beside the bundle preserves the same bytes and enters no history.
for d in "$DEV"/*/; do
    name=$(basename "$d")
    [ -d "$d/.git" ] || continue

    # NUL-delimited so paths with spaces survive
    mapfile -d '' -t untracked < <(
        git -C "$d" ls-files --others --exclude-standard -z 2>/dev/null
    )
    [ "${#untracked[@]}" -eq 0 ] && continue

    keep=()
    for p in "${untracked[@]}"; do
        case "${p,,}" in
            *.env|env.env|*secret*|*token*|*credential*|*password*|*.pem|*.key|*apikey*|*api_key*|*cookie*)
                echo "  SKIP (credential-shaped) $name/$p"
                continue
                ;;
        esac
        keep+=("$p")
    done
    [ "${#keep[@]}" -eq 0 ] && continue

    printf '%s\0' "${keep[@]}" \
        | tar -C "$d" --null -T - -czf "$OUT/$name.untracked.tar.gz" 2>/dev/null
    if [ -s "$OUT/$name.untracked.tar.gz" ]; then
        printf "  ok %-28s %s (%d files)\n" "$name" \
            "$(du -h "$OUT/$name.untracked.tar.gz" | cut -f1)" "${#keep[@]}"
    fi
done

echo
echo "Verifying..."
for b in "$OUT"/*.bundle; do
    [ -e "$b" ] || continue
    if git bundle verify "$b" >/dev/null 2>&1; then
        printf "  ok %s\n" "$(basename "$b")"
    else
        echo "  CORRUPT $(basename "$b")"
        fail=1
    fi
done

echo
echo "Bundles in $OUT"
echo "Untracked files are NOT in the bundles or the patches - see *.untracked.txt"
echo "and copy those paths separately if they matter."
[ "$fail" = "0" ] && echo "All good." || echo "Some failures above - do not wipe until resolved."
exit "$fail"
