import os
import json
import yaml
import subprocess
from datetime import datetime

from dotenv import load_dotenv
from git import Repo
from openai import OpenAI

load_dotenv()

STATE_FILE = ".newspyper_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

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

def summarize_with_gpt(client, repo_info):
    if not repo_info['diff'].strip() and not repo_info['commits'].strip():
        return "No significant changes found between specified commits."

    prompt = f"""
    You are a technical writer. Summarize the changes for the repository '{repo_info['name']}'.
    Repository URL: {repo_info['url']}
    Date of Analysis: {repo_info['date']}

    Below is the list of new commits and the combined diff. 
    Use this information to provide a natural-language summary of what changed.

    NEW COMMITS:
    {repo_info['commits']}

    DIFF DATA:
    {repo_info['diff'][:4000]} # Truncated to avoid token limits

    Instructions:
    1. Provide a natural-language summary of what changed.
    2. Use Markdown formatting.
    3. Be concise but informative.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def main():
    config = load_config()
    client = OpenAI()
    state = load_state()
    
    root_dir = config['repos_root']
    subfolders = [os.path.join(root_dir, f) for f in os.listdir(root_dir) 
                  if os.path.isdir(os.path.join(root_dir, f))]

    final_report = f"# Multi-Repo Change Summary - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    has_changes = False

    for folder in subfolders:
        if not os.path.exists(os.path.join(folder, ".git")):
            continue
            
        print(f"Processing {os.path.basename(folder)}...")
        repo_data = get_repo_diff(folder, state)
        
        if repo_data:
            if (repo_data['diff'] and repo_data['diff'].strip()) or (repo_data['commits'] and repo_data['commits'].strip()):
                summary = summarize_with_gpt(client, repo_data)
                final_report += f"## {repo_data['name']}\n"
                final_report += f"**Remote:** {repo_data['url']}\n\n"
                final_report += f"{summary}\n\n"
                final_report += "---\n\n"
                has_changes = True
            
            # Update state with the latest commit
            state[repo_data['name']] = repo_data['current_commit']

    if not has_changes:
        final_report += "No new commits across all tracked repositories.\n"

    save_state(state)

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

    # Open on Mac if requested
    if config.get('open_on_complete'):
        subprocess.run(["open", timestamped_output_path])


if __name__ == "__main__":
    main()