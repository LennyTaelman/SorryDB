# Use an official lightweight Python image
FROM python:3.13-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN useradd -m sorrydbuser

# Switch to sorrydbuser to install Lean
# Do this before installing sorrydb so that we can leverage Docker caching the container layer
USER sorrydbuser

# Install Lean
RUN curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- --default-toolchain stable -y

# Set up environment variables for Lean
ENV PATH="/home/sorrydbuser/.elan/bin:${PATH}"

# Verify Lean installation. Also this prompts elan to download stable version of Lean.
RUN lean --version

# Switch back to root user to install poetry and sorrydb
USER root

# Set working directory
WORKDIR /app

# Install Poetry
RUN pip install poetry

# Set environment variables for Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Copy project files
COPY pyproject.toml poetry.lock ./

# Poetry complains if there is no README.md file
RUN touch README.md

# Run poetry with `--no-root` to only install deps
RUN poetry install --without dev --no-root && rm -rf $POETRY_CACHE_DIR

# Copy source files and repo_lists
COPY sorrydb ./sorrydb
COPY data/repo_lists .data/repo_lists

# Install sorrydb
RUN poetry install --without dev

# Set ownership for non-root user
RUN chown -R sorrydbuser:sorrydbuser /app

# Switch to non-root user
USER sorrydbuser

