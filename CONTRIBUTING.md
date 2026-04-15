# Contributing to DataSpoc Pipe

Thank you for your interest in contributing! DataSpoc Pipe is maintained by a single developer, so all contributions go through pull requests.

## How to contribute

1. **Fork** the repository
2. **Create a branch** from `main` (`git checkout -b my-feature`)
3. **Make your changes**
4. **Run the tests**: `pytest tests/ -v`
5. **Push** to your fork and **open a Pull Request** against `main`

## Guidelines

- Keep PRs focused -- one feature or fix per PR
- Follow existing code style (Python 3.10+, Typer, Pydantic)
- Add tests for new functionality
- CLI messages in English
- No secrets in code -- use environment variables or cloud IAM

## What gets accepted

- Bug fixes with a clear description of the problem
- Documentation improvements
- New Singer tap templates
- Performance improvements
- Test coverage improvements

## What won't be accepted

- DAG/orchestration features (out of scope)
- Web UI (this is CLI-only)
- Breaking changes to the bucket convention without discussion
- Dependencies on heavy frameworks

## Reporting bugs

Open an [issue](https://github.com/dataspoclab/dataspoc-pipe/issues) with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- DataSpoc Pipe version (`dataspoc-pipe --version`)

## Code of Conduct

Be respectful. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).
