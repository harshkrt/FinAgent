# --- Stage 1: Builder ---
# This stage installs dependencies and builds our Python wheel.
FROM python:3.11-slim as builder

# Set the working directory
WORKDIR /app

# Install poetry for robust dependency management
# Using poetry is a best practice over requirements.txt for complex projects
RUN pip install poetry

# Copy only the files needed for dependency installation
# This leverages Docker's layer caching.
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.in-project true \
    && poetry install --no-root --without dev
# Install dependencies without installing the project itself
# --no-root prevents installing the 'finagent' package in this stage
# We only want the dependencies cached.

RUN poetry install --no-root --without dev
# --- Stage 2: Final Image ---
# This stage creates the final, lean image for running the application.
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /app

# Copy the installed virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Activate the virtual environment for subsequent RUN/CMD commands
ENV PATH="/app/.venv/bin:$PATH"

# Create a non-root user for security
RUN addgroup --system app && adduser --system --group app
USER app

# Copy the application source code
COPY ./src ./src

# The command to run the application using a production-grade server (Gunicorn)
# This replaces `uvicorn --reload`
CMD ["gunicorn", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "src.api.main:app", "--bind", "0.0.0.0:8000"]