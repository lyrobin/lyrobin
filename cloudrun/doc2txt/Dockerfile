# Use the official Google Cloud Run image as the base
FROM gcr.io/google.com/cloudsdktool/cloud-sdk:latest

RUN apt-get update
# Install LibreOffice and its dependencies
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-l10n-en-us \
    && rm -rf /var/lib/apt/lists/*

# Set up Python environment
RUN apt-get update && apt-get install -y python3 python3-pip

# # (Optional) Create a virtual environment
# RUN python3 -m venv /env
# ENV PATH="/env/bin:$PATH"

RUN apt-get update && apt-get install -y locales
RUN sed -i -e 's/# zh_TW.UTF-8 UTF-8/zh_TW.UTF-8 UTF-8/' /etc/locale.gen && locale-gen
ENV LANG zh_TW.UTF-8
ENV LANGUAGE zh_TW:en
ENV LC_ALL zh_TW.UTF-8

# Install Python dependenciesd
COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# Copy your application code
COPY . /app
WORKDIR /app

# (Optional) Set non-root user to run your application (recommended for security)
RUN useradd -ms /bin/bash appuser
USER appuser

# Expose the port your application listens on
EXPOSE 8080

# Start your Python application
CMD ["python3", "app.py"]
