# Browser and fonts come with this image, which is why we use it on Render/Railway/Fly.
FROM mcr.microsoft.com/playwright/python:v1.56.0-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY *.py index.html ./
ENV TREMOR_DATA=/data
CMD ["python", "server.py"]
