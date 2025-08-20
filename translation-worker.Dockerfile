# Use the official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY translation_worker_azure.py .

# Copy .env if it exists, create empty one if not
COPY .env* ./
RUN if [ ! -f .env ]; then touch .env; fi

# Run the worker application
CMD ["python", "translation_worker_azure.py"]
