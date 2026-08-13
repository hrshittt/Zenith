# Agentic Financial Decision Twin

This repository contains the full stack for the Agentic Financial Decision Twin demo.
The frontend is built with pure Vanilla HTML/CSS/JS and the backend is a Python FastAPI application implementing a multi-agent orchestration pattern.

## Prerequisites

- Python 3.10+
- A Groq API key for the AI orchestration layer

## Setup

1. **Configure Environment Variables**
   Navigate to the `backend` directory and copy `.env.example` to `.env`:
   ```bash
   cp backend/.env.example backend/.env
   ```
   Edit `backend/.env` and insert your `GROQ_API_KEY`.

2. **Install Backend Dependencies**
   ```bash
   cd backend
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On Mac/Linux:
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Seed the Database**
   The database needs to be populated with the initial user profiles (Individual, Startup, Enterprise). From the ROOT project directory, run:
   ```bash
   # Make sure your virtual environment is active!
   # On Windows:
   $env:PYTHONPATH="."
   python backend/seed.py
   # On Mac/Linux:
   PYTHONPATH="." python backend/seed.py
   ```

## Running the Application

To run the application, you need to start both the backend API server and serve the frontend static files.

### Start the Backend
From the root directory:
```bash
# On Windows:
$env:PYTHONPATH="."
uvicorn backend.main:app --reload --port 8000
```
The API will be available at `http://localhost:8000`. You can view the API documentation at `http://localhost:8000/docs`.

### Serve the Frontend
Open a new terminal in the `twin-app` directory and start a simple HTTP server:
```bash
cd twin-app
python -m http.server 3000
```
Open `http://localhost:3000` in your web browser. The frontend will now pull data dynamically from the FastAPI backend and use the agentic AI pipeline!
