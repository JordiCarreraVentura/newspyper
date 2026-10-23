import os
import sys
import json
import yaml
import shutil
import subprocess
from datetime import datetime, timezone

from dotenv import load_dotenv
from git import Repo
from openai import OpenAI

load_dotenv()

# Registry of supported LLM providers. Both are reached through the same OpenAI
# SDK; DeepSeek only differs by its base_url, default model and thinking toggle.
PROVIDERS = {
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url": None,
        "default_model": "gpt-6.1-sol",
        "extra_body": None,
    },
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-v4-pro",
        "extra_body": {"thinking": {"type": "enabled"}},
    },
}

# The model replies with exactly this line when a set of changes contains nothing
# worth reporting (e.g. only bug fixes, CI or version bumps). It lets us skip the
# whole repository section instead of emitting an empty heading.
NOTHING_NOTABLE = "Nothing notable to report."

# Upper bound on how many characters of a diff are sent to the model. Modern
# models have very large context windows, so this can be raised freely: a larger
# budget means fewer changes are silently dropped from the summary.
MAX_DIFF_CHARS = 40000


def resolve_provider_model(config):
    """Return (provider_name, provider_spec, model) for the configured provider."""
    provider = (config.get("provider") or "openai").lower()
    if provider not in PROVIDERS:
        raise SystemExit(
            f"Unknown provider '{provider}'. Choose one of: {', '.join(PROVIDERS)}."
        )
    spec = PROVIDERS[provider]
    model = config.get("model") or spec["default_model"]
    return provider, spec, model


def load_state(state_file):
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_state(state, state_file):
    with open(state_file, "w") as f:
        json.dump(state, f, indent=4)

def open_report(file_path):
    if sys.platform == "darwin":
        command = ["open", file_path]
    elif sys.platform.startswith("linux"):
        if not shutil.which("xdg-open"):
            print("Warning: 'xdg-open' not found, cannot open the report.")
            return
        command = ["xdg-open", file_path]
    elif sys.platform.startswith("win"):
        os.startfile(file_path)
        return
    else:
        print(f"Warning: no supported command to open the report on {sys.platform}.")
        return
    try:
        subprocess.run(command, check=False)
    except Exception as e:
        print(f"Warning: failed to open the report: {e}")

def get_last_commit_date(repo_path):
    try:
        repo = Repo(repo_path)
        return repo.head.commit.committed_datetime
    except Exception:
        return None

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def get_repo_diff(repo_path, state):
    try:
        repo = Repo(repo_path)
        # Fetching remote URL (usually 'origin')
        remote_url = next(repo.remote().urls, "No remote found")
        repo_name = os.path.basename(repo_path)
        
        try:
            current_commit = repo.head.commit.hexsha
        except ValueError:
            # Handle empty repositories with no commits
            return None
            
        last_commit = state.get(repo_name)
        
        if last_commit == current_commit:
            return None # No new commits since last check
            
        commits = []
        if last_commit:
            try:
                # Verify last_commit exists in the current history
                repo.commit(last_commit)
                # Get all commits between last_commit and current_commit
                commits = list(repo.iter_commits(f"{last_commit}..{current_commit}"))
                diff_text = repo.git.diff(last_commit, current_commit)
            except Exception:
                # Fallback if last_commit is unreachable (e.g. rebase)
                commits = list(repo.iter_commits(current_commit, max_count=5))
                try:
                    diff_text = repo.git.diff("HEAD~1", current_commit)
                except Exception:
                    diff_text = repo.git.diff("4b825dc642cb6eb9a060e54bf8d69288fbee4904", current_commit)
        else:
            # No state, get the latest commit's diff and summary
            commits = list(repo.iter_commits(current_commit, max_count=1))
            try:
                diff_text = repo.git.diff("HEAD~1", current_commit)
            except Exception:
                # Fallback for the first commit ever
                diff_text = repo.git.diff("4b825dc642cb6eb9a060e54bf8d69288fbee4904", current_commit)
        
        commit_messages = "\n".join([f"- {c.summary} ({c.hexsha[:7]})" for c in commits])
        
        return {
            "name": repo_name,
            "url": remote_url,
            "diff": diff_text,
            "commits": commit_messages,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "current_commit": current_commit
        }
    except Exception as e:
        print(f"Skipping {repo_path}: {e}")
        return None

SYSTEM_PROMPT = f"""You are a technical writer producing a factual change summary for a \
personal multi-repository newsletter. You are given the new commits and the combined git diff \
for a single repository. Summarize only what the commits and diff actually show.

Follow these rules exactly:

1. Output Markdown only. Do NOT wrap the whole answer in a ```markdown fence. Use inline code
   formatting (single backticks) for identifiers such as file paths, symbols and commands.
2. Start directly with the first fact. Never add an introductory sentence, a heading such as
   "New Features", a "Summary:" label, or any closing remark.
3. Report facts only. Never speculate, never say a detail "is not provided", "is unclear" or
   "cannot be determined", and never offer opinions or recommendations.
4. Write the report as bullet points. Indent nested bullets with exactly 3 spaces and leave a
   blank line between top-level bullet groups.
5. Report every new feature, capability, API, tool, skill or notable content addition.
6. Do NOT mention bug fixes, maintenance, refactors, version bumps, dependency updates, CI/CD,
   documentation-only edits, or formatting/whitespace changes.
7. If the changes contain nothing covered by rule 5, reply with exactly this line and nothing
   else: "{NOTHING_NOTABLE}"

Worked example
--------------
Given a diff that adds a `--json` flag and removes a retry loop, the correct output is:

- Added the `--json` flag to emit machine-readable output.

The incorrect output would mention the removed retry loop, add a "Changes" heading, or claim
that some information "was not provided". Match the correct style.
"""


def build_client(config):
    """Create an OpenAI SDK client for the configured provider."""
    provider, spec, _ = resolve_provider_model(config)
    api_key = os.getenv(spec["api_key_env"])
    if not api_key:
        raise SystemExit(
            f"Missing {spec['api_key_env']} for provider '{provider}'. "
            "Add it to your .env file (see env_template)."
        )
    kwargs = {"api_key": api_key}
    if spec["base_url"]:
        kwargs["base_url"] = spec["base_url"]
    return OpenAI(**kwargs)


def build_user_message(repo_info):
    return f"""Repository: {repo_info['name']}
URL: {repo_info['url']}
Date of analysis: {repo_info['date']}

New commits:
{repo_info['commits']}

Combined diff:
{repo_info['diff'][:MAX_DIFF_CHARS]}"""


def summarize_with_model(client, config, repo_info):
    if not repo_info['diff'].strip() and not repo_info['commits'].strip():
        return NOTHING_NOTABLE

    _, spec, model = resolve_provider_model(config)

    request = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(repo_info)},
        ],
    }

    effort = config.get("reasoning_effort")
    if effort:
        request["reasoning_effort"] = effort
    if spec["extra_body"]:
        request["extra_body"] = spec["extra_body"]

    response = client.chat.completions.create(**request)
    content = (response.choices[0].message.content or "").strip()
    return content or NOTHING_NOTABLE


def main():
    config = load_config()
    state_file = config.get('state_file', ".newspyper_state.json")

    provider, _, model = resolve_provider_model(config)
    client = build_client(config)
    print(f"Provider: {provider} | Model: {model}")

    state = load_state(state_file)

    blacklist = config.get('blacklist', []) or []
    if all(isinstance(item, dict) for item in blacklist):
        blacklisted_names = {item.get('name') for item in blacklist if item.get('name')}
    else:
        blacklisted_names = {str(item) for item in blacklist}
    
    root_dir = config['repos_root']
    subfolders = [os.path.join(root_dir, f) for f in os.listdir(root_dir) 
                  if os.path.isdir(os.path.join(root_dir, f))]

    final_report = f"# Multi-Repo Change Summary - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    has_changes = False

    inactive_days = config.get('inactive_days', 90)
    now = datetime.now(timezone.utc)
    inactive = []

    for folder in subfolders:
        if not os.path.exists(os.path.join(folder, ".git")):
            continue
            
        repo_name = os.path.basename(folder)
        print(f"Processing {repo_name}...")
        repo_data = get_repo_diff(folder, state)

        if repo_name not in blacklisted_names:
            last_commit_date = get_last_commit_date(folder)
            if last_commit_date and (now - last_commit_date).days >= inactive_days:
                inactive.append((repo_name, last_commit_date.date().isoformat()))
        
        if repo_data:
            if repo_name not in blacklisted_names:
                if (repo_data['diff'] and repo_data['diff'].strip()) or (repo_data['commits'] and repo_data['commits'].strip()):
                    summary = summarize_with_model(client, config, repo_data)
                    if summary.rstrip('.').strip().lower() == NOTHING_NOTABLE.rstrip('.').lower():
                        print(f"  No notable changes in {repo_name}.")
                    else:
                        final_report += f"## {repo_data['name']}\n"
                        final_report += f"**Remote:** {repo_data['url']}\n\n"
                        final_report += f"{summary}\n\n"
                        final_report += "---\n\n"
                        has_changes = True
            
            # Update state with the latest commit
            state[repo_data['name']] = repo_data['current_commit']

    if not has_changes:
        final_report += "No notable changes across all tracked repositories.\n"

    if blacklisted_names:
        final_report += "\n## Excluded repositories\n"
        for name in sorted(blacklisted_names):
            final_report += f"- {name}\n"

    if inactive:
        inactive.sort(key=lambda x: (x[1], x[0]))
        final_report += "\n## Inactive repositories\n"
        for name, last_update in inactive:
            final_report += f"- {name} (last updated: {last_update})\n"

    save_state(state, state_file)

    # Generate a timestamped filename so we don't overwrite previous runs
    base_path, ext = os.path.splitext(config['output_path'])
    if "weekly_" in base_path:
        base_path = base_path.replace("weekly_", "")
        
    timestamp = datetime.now().strftime("%Y-%m-%d")
    timestamped_output_path = f"{base_path}_{timestamp}{ext}"

    # Save the file
    with open(timestamped_output_path, "w") as f:
        f.write(final_report)

    print(f"Summary saved to {timestamped_output_path}")

    # Open the report automatically if requested
    if config.get('open_on_complete'):
        open_report(timestamped_output_path)


if __name__ == "__main__":
    main()
