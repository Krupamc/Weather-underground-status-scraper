# Builds docker image

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBEFFERED=1
ENV TZ=America/New_York

WORKDIR /app

# Update system
RUN apt-get update

# Install Timezone info
RUN apt-get install -y tzdata --no-install-recommends
        
# Delete the apt lists to save space 
RUN rm -rf /var/lib/apt/lists*

# Copy the file to working dir
COPY requirements.txt /app/requirements.txt

# Update pip (flag removes the cached packets)
RUN pip install --no-cache-dir --upgrade pip

# Install depends
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy web project over
COPY app/ /app/

# Copy scraper code:
COPY status_scraper/ /app/status_scraper/

# Copy weather scraper code if it is in its own folder:
COPY weather_scraper/ /app/weather_scraper/

# Copy scheduled-runner script:
COPY scripts/ /app/scripts/

#RUN mkdir -p

# Open the 800 port for FastAPI
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]