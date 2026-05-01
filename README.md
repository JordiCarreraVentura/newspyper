# Newspyper

## User specifications (_prompt_)

Consider the folder of repositories shown below. I need a Python script

1. With a YAML config file where I can specify the location of this folder.
2. Tracks the last processed commit for each repository using a state file (`.newspyper_state.json`).
3. On each run, collects all new commits and the combined diff since the last execution.
4. Sends the commit history and diff, along with repository information (name, URL) and date, to OpenAI's GPT-4o to generate a natural-language summary.
5. Concatenates all summaries into a single Markdown report, organized by repository.
6. Saves the summary to a timestamped file (e.g., `weekly_summary_2024-04-29.md`).
7. Optionally opens the report automatically on Mac.

```
repos
├── DevOps-Roadmap
├── Prompt-Engineering-Guide
├── The-Complete-FAANG-Preparation
├── awesome-datascience
├── awesome-devops
├── awesome-llm-apps
├── awesome-mac
├── awesome-production-machine-learning
├── awesome-python
├── claude-quickstarts
├── developer-roadmap
├── free-for-dev
├── open-source-mac-os-apps
├── papers-we-love
├── professional-programming
└── the-incredible-pytorch
```


## Installation

1. Duplicate `config_template.yaml` as `config.yaml`.
2. Set the values.
3. Run `make install`.


## Release

If any dependencies are required, edit the `pyproject.toml` file, `[project]` field, and add a `dependencies` key with a `List[str]` value, where each string is a `pip`-readable dependency.

```
# Build the package before uploading (from the package's root folder)
$ python -m build 

# Upload the package to pypi
$ python -m twine upload --repository pypi dist/*
```