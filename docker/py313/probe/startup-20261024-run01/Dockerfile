FROM ltdps/edxapp:py313-local-dev
RUN apt-get update -qq && apt-get install -y --no-install-recommends libglib2.0-0 libx11-6 libxext6 libxrender1 gettext && rm -rf /var/lib/apt/lists/*
RUN pip install uv
