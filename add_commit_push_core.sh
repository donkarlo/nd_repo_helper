#!/usr/bin/env bash
# Safely commit and synchronize each repository without overwriting remote history.

set -uo pipefail
export GIT_PAGER=cat

REPOSITORIES_ROOT="${ND_REPO_ROOT:-${HOME}/Dropbox/repo}"
REMOTE="${ND_REPO_REMOTE:-mghub}"
BRANCH="${ND_REPO_BRANCH:-main}"
FAILED=0
SYNCHRONIZED=0
SKIPPED=0

if ! cd "$REPOSITORIES_ROOT"; then
    printf 'ERROR: Repository root does not exist: %s\n' "$REPOSITORIES_ROOT" >&2
    exit 1
fi

shopt -s nullglob
for directory in */; do
    repository="${REPOSITORIES_ROOT%/}/${directory%/}"
    if [[ ! -d "$repository/.git" ]]; then
        continue
    fi

    printf '\n📁 Syncing repository: %s\n' "$directory"
    current_branch="$(git -C "$repository" symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
    if [[ "$current_branch" != "$BRANCH" ]] && ! git -C "$repository" checkout "$BRANCH"; then
        printf 'ERROR: Cannot switch %s to %s. Repository left untouched.\n' "$directory" "$BRANCH" >&2
        FAILED=1
        continue
    fi

    # Never stage an unfinished merge: doing so can commit conflict markers.
    if [[ -n "$(git -C "$repository" ls-files -u)" ]]; then
        printf 'ERROR: %s has unresolved merge conflicts; finish or abort that merge first.\n' "$directory" >&2
        FAILED=1
        continue
    fi

    if ! git -C "$repository" add --all; then
        printf 'ERROR: Cannot stage changes in %s.\n' "$directory" >&2
        FAILED=1
        continue
    fi

    if ! git -C "$repository" diff --cached --quiet; then
        printf '📝 Changes staged for commit in %s:\n' "$directory"
        git -C "$repository" --no-pager diff --cached --name-only
        printf 'Do you want to commit and push these changes? [y/N]: '
        if ! IFS= read -r confirmation; then
            printf '\nERROR: Input ended before the confirmation; changes remain staged.\n' >&2
            FAILED=1
            continue
        fi
        case "$confirmation" in
            [Yy])
                printf 'Enter commit message: '
                if ! IFS= read -r message || [[ -z "$message" ]]; then
                    printf '\nERROR: A commit message is required; changes remain staged.\n' >&2
                    FAILED=1
                    continue
                fi
                if ! git -C "$repository" commit -m "$message"; then
                    printf 'ERROR: Commit failed in %s; changes remain available locally.\n' "$directory" >&2
                    FAILED=1
                    continue
                fi
                ;;
            *)
                printf '⏭️ Skipped %s at user request. No push attempted.\n' "$directory"
                SKIPPED=$((SKIPPED + 1))
                continue
                ;;
        esac
    else
        printf '✔️ No new changes to commit in %s. Checking earlier commits.\n' "$directory"
    fi

    if ! git -C "$repository" remote get-url "$REMOTE" >/dev/null; then
        printf 'ERROR: Remote %s is missing in %s; local commits are safe.\n' "$REMOTE" "$directory" >&2
        FAILED=1
        continue
    fi

    # Fetch even when there were no new changes: a failed prior push can leave
    # many local commits waiting to be published for weeks.
    if ! git -C "$repository" fetch --no-tags "$REMOTE" "$BRANCH"; then
        # An empty new repository has no main branch yet. Distinguish this
        # from a real transport/authentication failure before first push.
        if git -C "$repository" ls-remote --exit-code --heads "$REMOTE" "refs/heads/$BRANCH" >/dev/null 2>&1; then
            printf 'ERROR: Fetch failed in %s even though the remote branch exists.\n' "$directory" >&2
            FAILED=1
            continue
        else
            remote_status=$?
        fi
        if (( remote_status == 2 )); then
            printf '⬆️  Publishing initial %s branch in %s.\n' "$BRANCH" "$directory"
            if git -C "$repository" push "$REMOTE" "HEAD:refs/heads/$BRANCH"; then
                printf '✅ Synchronized %s\n' "$directory"
                SYNCHRONIZED=$((SYNCHRONIZED + 1))
            else
                printf 'ERROR: Initial push failed in %s; commits remain local.\n' "$directory" >&2
                FAILED=1
            fi
        else
            printf 'ERROR: Fetch failed in %s; no push attempted. Check network and remote.\n' "$directory" >&2
            FAILED=1
        fi
        continue
    fi

    difference="$(git -C "$repository" rev-list --left-right --count HEAD...FETCH_HEAD)"
    if ! read -r ahead behind <<< "$difference" ||
        [[ ! "$ahead" =~ ^[0-9]+$ ]] || [[ ! "$behind" =~ ^[0-9]+$ ]]; then
        printf 'ERROR: Could not compare local and remote commits for %s.\n' "$directory" >&2
        FAILED=1
        continue
    fi

    if (( behind > 0 && ahead > 0 )); then
        printf 'ERROR: %s has %d local-only and %d GitHub-only commits.\n' "$directory" "$ahead" "$behind" >&2
        printf '       Push skipped to protect both histories. Merge manually; never force-push.\n' >&2
        FAILED=1
        continue
    fi

    if (( behind > 0 )); then
        printf '⬇️  Fast-forwarding %s by %d remote commit(s).\n' "$directory" "$behind"
        if ! git -C "$repository" merge --ff-only FETCH_HEAD; then
            printf 'ERROR: Could not fast-forward %s; remote and local contents kept.\n' "$directory" >&2
            FAILED=1
            continue
        fi
        ahead=0
    fi

    if (( ahead > 0 )); then
        printf '⬆️  Pushing %d local commit(s) from %s.\n' "$ahead" "$directory"
        if ! git -C "$repository" push "$REMOTE" "HEAD:refs/heads/$BRANCH"; then
            printf 'ERROR: Push failed in %s. Commits remain on this computer.\n' "$directory" >&2
            FAILED=1
            continue
        fi
    fi

    printf '✅ Synchronized %s\n' "$directory"
    SYNCHRONIZED=$((SYNCHRONIZED + 1))
done

printf '\nSync summary: %d synchronized, %d skipped.\n' "$SYNCHRONIZED" "$SKIPPED"
if (( FAILED != 0 )); then
    printf 'ERROR: At least one repository was NOT synchronized. Review the errors above.\n' >&2
    exit 1
fi
printf 'All selected repositories are synchronized with their remotes.\n'
