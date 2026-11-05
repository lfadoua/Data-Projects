# Git line endings and whitespace: Windows / WSL follow-up

Reviewed 31 October 2026, in the same parent Git repository used by the
[GitHub readiness report](github-readiness-report.md).

## Result

`git diff --check` now returns **0 with no trailing-whitespace diagnostics** in
both Git for Windows and Ubuntu/WSL. The staged check also returns 0; no files
were staged. No commit or push was made.

The correction is one additional rule in the root `.gitattributes`:

```gitattributes
*.css text eol=lf
```

No Python, requirements, CSS, Docker, data or real `.env` file was rewritten by
this follow-up. The other edits are this report and its link in the readiness
report. The previously prepared README, storytelling and validation work remains
in place.

## Configuration and actual cause

| Item | Git for Windows | Git inside Ubuntu/WSL |
|---|---|---|
| Repository | Parent `Data Job Market Intelligence` | The same checkout under `/mnt/c/Users/HP/Documents/Data Projects/Data Job Market Intelligence` |
| `core.autocrlf` | `true`, from the Windows system Git configuration | Not explicitly configured |
| `core.whitespace` | Not explicitly configured | Not explicitly configured |
| `core.eol`, `core.safecrlf` | Not explicitly configured | Not explicitly configured |
| Applicable attributes | Root `.gitattributes`, already defining LF text for Python, Markdown, YAML, JSON, SQL and requirements text | The same file and rules |

The initial native Windows check returned 0. That did not establish that WSL
would behave identically. The WSL check reproduced a real failing diagnostic:

```text
data-job-market-intelligence/app/assets/theme.css:227: trailing whitespace.
```

The file's last empty line contained bytes **0D 0A** (CRLF), while the version in
Git's index used LF. That was the only CRLF sequence in this CSS file. There
were **no trailing spaces or tabs** in it, and its entire content matched the
index exactly after CRLF → LF normalization.

The CSS extension was missing from the explicit text-normalization rules.
Windows' `core.autocrlf=true` normalized the carriage return before comparison.
WSL did not have that setting, so it saw the remaining carriage return on the
added blank line as trailing whitespace. Adding the CSS attribute makes Git
normalize that text consistently before comparing it, without modifying the
actual stylesheet.

In the current checkout, WSL reproduced this one remaining trailing-whitespace
failure, not a fresh failure in every Python or requirements file. The numerous
other messages were **conversion notices**, such as:

```text
warning: ... CRLF will be replaced by LF the next time Git touches it
```

Those notices describe normalization of existing Windows working-tree files;
they are different from a `path:line: trailing whitespace` error. The earlier
large filename list cannot be reconstructed from a filtered command alone, but
the current Windows and WSL checks are recorded separately below.

## Why this is the smallest correction

- One attribute handles the uncovered CSS case for both Git clients.
- The stylesheet itself remains byte-identical; there is no visual or runtime change.
- No bulk Python normalization, `git add --renormalize`, reset, checkout or
  history rewrite was used.
- No global/local `core.whitespace` change was made to hide errors, and conversion
  warnings were not suppressed with `core.safecrlf` configuration.
- Actual `.env` files retain the existing `-text` exclusion and remain ignored.

Previously modified/new files had received documented line-ending normalization
in the earlier readiness work. This follow-up performs **no further source-file
normalization**. All already-tracked file bytes were compared with a snapshot
taken at the beginning of this follow-up and remained unchanged.

## Final verification

| Command / environment | Exit | Trailing-whitespace diagnostics |
|---|---:|---:|
| `git diff --check`, Windows | 0 | 0 |
| `git diff --check`, Ubuntu/WSL | 0 | 0 |
| `git diff --cached --check`, Ubuntu/WSL | 0 | 0 |

The exact original `grep | cut | sort` command was also executed from the
application directory in Ubuntu. It returned no filenames, no stderr and exit 0.

Harmless conversion notices can still appear for existing CRLF working-tree
files. They were deliberately left visible rather than rewriting dozens of
untouched files merely to silence them. No genuine added-line whitespace error
remains in either Git check.

From the application directory, use the unfiltered command to see Git's result.
In PowerShell:

```powershell
git -C .. diff --check
$LASTEXITCODE
```

In Ubuntu:

```bash
git -C .. diff --check
printf 'Git exit status: %s\n' "$?"
```

The expected exit status is **0**. The original `grep | cut | sort` pipeline is
useful for listing matching messages, but its final exit status does not reliably
preserve Git's exit status. It also omits all nonmatching diagnostics.

The verification artifact is
`evaluation/results/git-line-ending-review-2026-10-31/verification.json` (local,
ignored). It contains both clients' raw results and byte-integrity checks for
`.env`, both Dockerfiles, both Compose files and `.dockerignore`. No secret
values are included.

Pytest was not rerun for an attribute/documentation-only correction. The earlier
**196-pass** run remains dated evidence, not a newly claimed execution.

## Publication and security

This formatting issue is resolved. It does not remove the outstanding action to
rotate the previously exposed PostgreSQL credential before public publication.
No rotation has been confirmed here. Hosted GitHub Actions also remains
unverified. Keep the readiness verdict **READY TO PUSH PRIVATELY, WITH REMAINING
SECURITY ACTIONS**, subject to the owner's final review.
