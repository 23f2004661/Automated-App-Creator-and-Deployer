🚀 Automatic App Builder & GitHub Deployment Service

This FastAPI service automates the full lifecycle of building and deploying frontend applications.
Given a task description, it uses an LLM to generate code, creates a GitHub repository, deploys the app to GitHub Pages, and updates it across multiple rounds.

✔️ What This Service Does
Round 1: Create & Deploy

Creates a new GitHub repository

Generates a complete frontend application using Gemini

Pushes all generated files (HTML, JS, README, LICENSE)

Enables GitHub Pages and sets up a deployment workflow

Notifies the evaluation server

Round 2: Update

Fetches existing files from GitHub

Sends current code + update instructions to the LLM

Updates the application

Pushes the new version

Notifies the evaluation server again

All long-running operations run asynchronously via FastAPI background tasks.

🛠️ Tech Stack

FastAPI

Google Gemini (genai)

GitHub REST API

Requests

Python 3.12+

dotenv

🔐 Environment Variables

Create a .env file:

GITHUB_TOKEN=your_github_pat
OWNER=your_github_username
TASK_SECRET=shared_secret
GEMINI_API_KEY=your_gemini_api_key

▶️ Run the Server
pip install -r requirements.txt
uvicorn main:app --reload


Server runs at:

http://localhost:8000

📬 API Endpoint
POST /handle_task

Payload:

{
  "email": "your-email",
  "secret": "task-secret",
  "task": "task-name",
  "round": 1,
  "nonce": "unique-id",
  "brief": "App description",
  "checks": [],
  "evaluation_url": "https://...",
  "attachments": []
}


round: 1 → create and deploy new app

round: 2 → update existing app

Response:

{ "status": "accepted", "task": "...", "round": 1 }

🌐 Output

Each run produces:

A GitHub repository

A deployed GitHub Pages site

Automatic CI/CD workflow

A fully generated or updated frontend application

