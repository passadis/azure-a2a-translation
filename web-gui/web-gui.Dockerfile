FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY translation_agent_card.json .
COPY entrypoint.sh .

# Copy templates and static directories
COPY templates/ templates/
COPY static/ static/

# Create necessary directories
RUN mkdir -p results

# Make entrypoint script executable
RUN chmod +x entrypoint.sh

# Expose port
EXPOSE 5000

# Use entrypoint script to update config and start app
ENTRYPOINT ["./entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
