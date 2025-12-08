# Releasing connect-python

This document outlines how to create a release of connect-python.

1. Clone the repo, ensuring you have the latest main.

2. On a new branch, update version strings with the `bump` command, either to the next minor or patch version, based on the changes that are included in this new release.

- If there are only bug fixes and no new features, run `uv run just bump patch`.
- If there are features being released, run `uv run just bump minor`.

Note the new version X.Y.Z in the updated files.

3. Open a PR titled "Prepare for vX.Y.Z" ([Example PR #60](https://github.com/connectrpc/connect-python/pull/60)) and assign the `connectrpc/python` group as reviewers. Once it's approved by at
   least one other maintainer and CI passes, merge it.

   _Make sure no new commits are merged until the release is complete._

4. Review all commits in the new release and for each PR check an appropriate label is used and edit the title to be meaningful to end users. This will help auto-generated release notes match the final notes as closely as possible.

5. Using the Github UI, create a new release.

   - Under “Select tag”, type in “vX.Y.Z” to create a new tag for the release upon publish.
   - Target the main branch.
   - Title the Release “vX.Y.Z”.
   - Click “set as latest release”.
   - Set the last version as the “Previous tag”.
   - Click “Generate release notes” to autogenerate release notes.
   - Edit the release notes. A summary and other sub categories may be added if required but should, in most cases, be left as ### Enhancements and ### Bugfixes. Feel free to collect multiple small changes to docs or Github config into one line, but try to tag every contributor. Make especially sure to credit new external contributors!

6. Publish the release.

[latest release]: https://github.com/connectrpc/connect-python/releases/latest
