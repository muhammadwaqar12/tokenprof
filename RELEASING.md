# Releasing

Publishing is deliberate: it happens on a version tag, never on a merge.

## One-time setup

PyPI uses trusted publishing, so no API token is stored anywhere.

1. Create a pending publisher at https://pypi.org/manage/account/publishing/
   - PyPI project name: `tokenprof`
   - Owner: `muhammadwaqar12`
   - Repository: `tokenprof`
   - Workflow: `release.yml`
   - Environment: `pypi`
2. In this repo: Settings → Environments → New environment → `pypi`.
   Adding yourself as a required reviewer there means every publish needs a
   click, which is worth it.

## Cutting a release

```bash
# bump the version in pyproject.toml, then
git commit -am "Release 0.1.0"
git tag v0.1.0
git push && git push --tags
```

The workflow refuses to publish if the tag and `pyproject.toml` disagree, runs
`twine check --strict`, and installs the built wheel and runs the CLI before
anything reaches PyPI.

## Do not publish before launch

The name is unclaimed and an unclaimed name cannot be taken from you in a week.
A `0.1.0` sitting on PyPI with no traffic behind it spends a first impression
for nothing, and a version number can never be reused once published.
