FROM python:3.11-slim-bookworm

# Install system dependencies for OpenCV, EasyOCR, ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy files to the container
COPY . .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Run your script
CMD ["python", "yt_signal.py"]
