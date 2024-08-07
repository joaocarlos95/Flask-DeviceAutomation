
FROM python:3.12

# Copy app files to /app directory in the container
COPY dep /app/dep
COPY inputfiles /app/inputfiles
COPY src /app/src
COPY main.py /app

# Set the working directory to /app
WORKDIR /app

# Create virtual environment to run the application
ENV VIRTUAL_ENV=/app/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask port 5000 for access outside the container
EXPOSE 5000

# Run the application
CMD ["python", "main.py"]