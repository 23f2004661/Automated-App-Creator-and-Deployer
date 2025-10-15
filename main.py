# /// script
# requires-python = ">=3.12"
# dependencies = ["requests","uvicorn","fastapi","dotenv","google-genai"]
# ///

# we are creating an application that will build, deploy and push and aplication

from fastapi import FastAPI,BackgroundTasks
from fastapi.responses import HTMLResponse
import os
import subprocess
import requests
import base64
from dotenv import load_dotenv
import json
import time
from google import genai
import re

app =FastAPI()

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head><title>Student Task Automation</title></head>
        <body>
            <h1>✅ FastAPI app is running!</h1>
            <p>Use the <a href='/docs'>API docs</a> to interact with endpoints.</p>
        </body>
    </html>
    """


load_dotenv()  # take environment variables from .env.  file

def get_file_sha(owner: str, repo: str, path: str, token: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("sha")
    return None

def get_sha_of_latest_commit(repo_name: str, branch: str = "main") -> str | None:
    print(repo_name)
    url = f"https://api.github.com/repos/{os.getenv('OWNER')}/{repo_name}/branches/{branch}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
    }

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"❌ Failed to get branch info: {response.status_code} - {response.text}")
        return None

    branch_data = response.json()
    sha = branch_data.get("commit", {}).get("sha")
    if sha:
        print(f"✅ Found '{branch}' branch with SHA: {sha}")
        return sha
    else:
        print(f"❌ Unexpected response format: {branch_data}")
        return None



# validate the secret sent using the env var TASK_SECRET
def validate_secret(secret: str):
    secret_env = os.getenv("TASK_SECRET")
    print(secret_env)
    if secret_env != secret:
        return False
    return True

def create_repo(repo_name: str):
#create a repo using the github api with a personal access token stored in env var

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set")
    else:
        try:
        #     subprocess.run(["gh", "repo", "create", repo_name, "--public"], check=True)
        #     print(f"Repository {repo_name} created successfully.")
        # except subprocess.CalledProcessError as e:
        #     print("Error creating repository:", e)
            url = f"https://api.github.com/user/repos"
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json"
            }
            payload = {
                "name": repo_name,
                "private": False,
                "auto_init": False
            }
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 201:
                print(f"✅ Repository {repo_name} created successfully.")
            else:
                try:
                    error = response.json()
                except ValueError:
                    error = response.text
                print(f"❌ Failed to create repository {repo_name}: {error}")
        except Exception as e:
            print("Unexpected error:", e)

def enable_github_page(repo_name: str):
    url = f"https://api.github.com/repos/{os.getenv('OWNER')}/{repo_name}/pages"
    headers = {
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github.json"
    }
    payload = {
        "build_type":"legacy",
        "source": {
            "branch": "main",
            "path": "/"
        }
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code in [201, 204]:
        print(f"✅ GitHub Pages enabled for {repo_name}")
    else:
        try:
            error = response.json()
        except ValueError:
            error = response.text
        print(f"❌ Failed to enable GitHub Pages for {repo_name}: {error}")


def setup_github_pages(repo_name: str):
    """
    Creates a GitHub Actions workflow that automatically enables and deploys to GitHub Pages
    """
    headers = {
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json"
    }
    
    # GitHub Actions workflow content
    workflow_content = """name: Deploy to GitHub Pages

on:
  push:
    branches: [ main, master ]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Pages
        uses: actions/configure-pages@v4
        with:
          enablement: true
      
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: '.'
      
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
"""
    
    workflow_path = ".github/workflows/deploy-pages.yml"
    
    payload = {
        "message": "Add GitHub Pages deployment workflow",
        "content": base64.b64encode(workflow_content.encode()).decode(),
    }
    
    url = f'https://api.github.com/repos/{os.getenv("OWNER")}/{repo_name}/contents/{workflow_path}'
    
    # Check if workflow already exists
    check_response = requests.get(url, headers=headers)
    if check_response.status_code == 200:
        payload["sha"] = check_response.json().get('sha')
        print(f"🔄 Updating existing workflow")
    
    response = requests.put(url, json=payload, headers=headers)
    
    if response.status_code in [200, 201]:
        print(f"✅ GitHub Pages workflow created")
        print(f"🌐 Site will be available at: https://{os.getenv('OWNER')}.github.io/{repo_name}/")
        print(f"⏳ Workflow will run automatically on next push")
        return True
    else:
        try:
            error = response.json()
        except ValueError:
            error = response.text
        print(f"❌ Failed to create workflow: {error}")
        return False

def push_to_repo(repo_name: str, files: str, round: int):
    if round == 2:
        branch="main"
        latest_sha=get_sha_of_latest_commit(repo_name)

    else: latest_sha = None

    headers ={
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github.json"
    }
    # based on the files list of objects with fields name and content push each file to the repo
    for file_obj in files:
        file = file_obj['name']
        content = file_obj['content']
        payload = {
            "message": f"Add {file} - round {round}",
            "content": base64.b64encode(content.encode()).decode(),
        }
        if latest_sha:
            payload["sha"] = latest_sha
        url=f'https://api.github.com/repos/{os.getenv("OWNER")}/{repo_name}/contents/{file}'
        response =requests.put(url, json=payload, headers=headers)
        if response.status_code in [200, 201]:
            print(f"✅ Pushed {file} to {repo_name}")
        else:
            try:
                error = response.json()
            except ValueError:
                error = response.text
            print(f"❌ Failed to push {file} to {repo_name}: {error}")

def push_to_repo2(repo_name: str, files: list[dict]):
    owner = os.getenv("OWNER")
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"}

    for file in files:
        path = file["name"]
        content = file["content"]
        file_sha = get_file_sha(owner, repo_name, path, token)

        url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}"
        payload = {
            "message": f"Round {round} update: {path}",
            "content": base64.b64encode(content.encode()).decode(),
            "sha": file_sha  # ✅ Use file-specific SHA
        }

        response = requests.put(url, headers=headers, json=payload)
        if response.status_code in [200, 201]:
            print(f"✅ Pushed {path} to {repo_name}")
        else:
            print(f"❌ Failed to push {path} to {repo_name}: {response.json()}")

def write_code_with_llm(data: dict):
    
    prompt = f"""You are a code generator. Build a Minimal app initialize it with a professional README.md and Add an MIT License.
create the app based on the following Tasks and build it completely on the frontend.
Task: {data["brief"]}
Attachments: {data["attachments"]}
Requirements: {data["checks"]}

This app will be deployed on GitHub Pages. Therefore:

- Only generate frontend code (HTML, JavaScript, README.md, LICENSE)
- All logic must be handled in JavaScript
- All functionality must run entirely in the browser
- The main entry point must be index.html

You MUST include the following files:
- index.html
- script.js (or equivalent JS file) (if necessary)
- README.md
- LICENSE (MIT License)

README.md must include:
- A clear summary of the app
- Setup instructions
- Usage guide
- Code explanation


Format your response EXACTLY as follows (no JSON, no extra text):

FILE: filename.js
    
    FILE: filename.js
```
    file content here
```
    
    FILE: another_file.html
```
    content here
```
    
    FILE: README.md
```
    readme content
```
    Important: 
    - Start each file with "FILE: filename"
    - Put code inside triple backticks
"""
        
    print("Requesting code generation from the model...")

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )
        
        print("Response received from the model.")
        
        # Parse the structured response
        files = []
        # Match FILE: filename followed by code block
        pattern = r'FILE:\s*(.+?)\s*\n```(?:\w+)?\s*\n(.*?)\n```'
        matches = re.findall(pattern, response.text, re.DOTALL)
        
        if not matches:
            print("❌ No files found in response. Trying alternative parsing...")
            # Save response for debugging
            with open("debug_response.txt", "w") as f:
                f.write(response.text)
            print("Response saved to debug_response.txt")
            return []
        
        for filename, content in matches:
            files.append({
                "name": filename.strip(),
                "content": content.strip()
            })
        
        print(f"✅ Parsed {len(files)} files:")
        for f in files:
            print(f"   - {f['name']}")
        
        return files
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []


def get_all_files_from_github(OWNER: str, repo: str, token: str, branch: str = "main") -> dict:
    headers = {"Authorization": f"Bearer {token}"}

    # Get latest commit SHA
    sha = get_sha_of_latest_commit(repo)
    if not sha:
        print("❌ Could not retrieve commit SHA. Aborting file fetch.")
        return {}

    # Get full file tree
    tree = None
    tree_url = f"https://api.github.com/repos/{OWNER}/{repo}/git/trees/{sha}?recursive=1"
    tree_resp = requests.get(tree_url, headers=headers)

    if tree_resp.status_code == 200:
        tree_json = tree_resp.json()
        if "tree" in tree_json:
            tree = tree_json["tree"]
            print("✅ Got the files from the tree")
        else:
            print(f"❌ Unexpected tree response format: {tree_json}")
            return {}
    else:
        print(f"❌ Failed to get file tree: {tree_resp.status_code} - {tree_resp.text}")
        return {}

    # Fetch and decode each file
    files = {}
    for item in tree:
        if item["type"] == "blob":
            path = item["path"]
            content_url = f"https://api.github.com/repos/{OWNER}/{repo}/contents/{path}"
            r = requests.get(content_url, headers=headers)
            if r.status_code == 200:
                encoded = r.json().get("content", "")
                decoded = base64.b64decode(encoded).decode("utf-8")
                files[path] = decoded
            else:
                print(f"⚠️ Failed to fetch {path}: {r.status_code}")

    return files




#create an endpoint that will update the files in the repo based upon the brief and then push the files to the repo
def update(data: dict, repo_name: str, previous_files: dict) -> list[dict]:
    file_context = ""
    for name, content in previous_files.items():
        file_context += f"\nHere is the current {name}:\n```\n{content}\n```"

    prompt=prompt = f"""You are a code generator. Modify or extend the existing frontend app based on this task.

Task: {data["brief"]}
Attachments: {data["attachments"]}
Requirements: {data["checks"]}

{file_context}

-Update the exisisting files based on the Task

-Generate complete, working code. Keep it simple and functional.

-Format your response EXACTLY as follows (no JSON, no extra text):

FILE: filename.js
    
    FILE: filename.js
```
    file content here
```
    
    FILE: another_file.html
```
    content here
```
    
    FILE: README.md
```
    readme content
```
    Important: 
    - Update Readme based on the changes made
"""
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(model="gemini-2.5-flash-lite", contents=prompt)

        # Parse response
        pattern = r'FILE:\s*(.+?)\s*\n```(?:\w*\n)?(.*?)```'
        matches = re.findall(pattern, response.text, re.DOTALL)

        files = [{"name": name.strip(), "content": content.strip()} for name, content in matches]
        print("returning files after updating")
        return files
    except Exception as e:
        print(e)




# notify the tester about all the things done in round 1 and round 2
def notify_server(data: dict, repo_name: str):
    url = data['evaluation_url']
    sha=get_sha_of_latest_commit(repo_name)

    payload = {
        "email": data["email"],
        "task": data["task"],
        "round": data["round"],
        "nonce": data["nonce"],
        "repo_url": f"https://github.com/{os.getenv('OWNER')}/{repo_name}",
        "commit_sha": sha,  # Ensure this is defined
        "pages_url": f"https://{os.getenv('OWNER')}.github.io/{repo_name}/"
    }
    headers = {
        "Content-Type": "application/json"
    }

    delay = 1
    for attempt in range(6):  # Max ~31s total wait
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                print("✅ Notified evaluation server")
                return True
            else:
                print(f"❌ Attempt {attempt+1} failed: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Attempt {attempt+1} exception: {e}")

        time.sleep(delay)
        delay *= 2

    print("❌ All attempts to notify evaluation server failed.")
    return False

#do all of this round 1:
def round_1(data: dict):
    repo_name = f'{data["task"]}-{data["nonce"]}'
    create_repo(repo_name)
    files = write_code_with_llm(data)
    print("got  the files from round 1")
    push_to_repo(repo_name,files,1)
    enable_github_page(repo_name)
    setup_github_pages(repo_name)
    notify_server(data, repo_name)

    
#round 2
def round_2(data: dict):
    repo_name= f'{data["task"]}-{data["nonce"]}'
    files=get_all_files_from_github(os.getenv("OWNER"),repo_name,os.getenv("GITHUB_TOKEN"))
    files1=update(data,repo_name,files)
    push_to_repo2(repo_name,files1)
    notify_server(data, repo_name)




# make an endpoint that accepts a json post with the following params: email, secret, task, round, nonce, brief, checks([]), evaluation url, attachments([object with feilds name and url])
@app.post("/handle_task")
def handle_task(data: dict, background_tasks: BackgroundTasks):
    if not validate_secret(data.get("secret")):
        return {"status": "error", "message": "Invalid secret"}

    if data.get("round") == 1:
        # ✅ Schedule round_1 to run in the bFackground
        print("round 1 started")
        background_tasks.add_task(round_1, data)

    elif data.get("round") == 2:
        print("round 2 started")
        # ✅ Schedule round_2 to run in the background
        background_tasks.add_task(round_2, data)

    # ✅ Immediately return HTTP 200 response
    return {"status": "accepted", "task": data["task"], "round": data["round"]},200




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0",port=8000)



