# Newspyper

[Link to GitHub repository](https://github.com/JordiCarreraVentura/newspyper)

## User specifications (_prompt_)

Consider the folder of repositories shown below. `newspyper`

1. Starts with a YAML config file where the user can specify the location of this source folder.
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
├── ...
├── free-for-dev
├── open-source-mac-os-apps
├── papers-we-love
├── professional-programming
└── the-incredible-pytorch
```


## Installation

1. Duplicate `config_template.yaml` as `config.yaml`.
   1. Set the value of the root folder containing the target repositories (`repos_root`).
   2. The output path (`output_path`) can remain the same. Change if there is a more suitable one.
   3. `open_on_complete = true` is currently supported only on Apple systems having the `open` command.
      It must be adapted for Ubuntu systems.
2. Duplicate `env_template` as `.env`.
   -  Set the value of the OpenAI API key.
3. Run `make install`.
4. Run `make run`.


## Next steps

1. Add support for **Ubuntu** systems in `open_on_complete`.
2. Alert the user about repositories that **haven't updated recently**.
3. Add support for **non-repository websites**.
4. Add a **table** with a structured recap of the summaries.
