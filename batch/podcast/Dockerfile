# Use the official Google Cloud Run image as the base
FROM gcr.io/google.com/cloudsdktool/cloud-sdk:latest

RUN apt install software-properties-common -y
RUN apt-get update
RUN apt-get install -y libcairo2-dev
RUN apt install -y ffmpeg
RUN apt-get install -y python3 python3-pip python3-dev python3-venv

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Copy  application code
COPY . /app
WORKDIR /app

CMD ["/opt/venv/bin/python", "main.py"]
