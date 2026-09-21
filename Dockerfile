# Builds docker image

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBEFFERED=1
ENV TZ=America/New_York

WORKDIR /app

# Update system
RUN apt-get update

# Install Timezone info
RUN apt-get install -y --no-install-recommends
        tzdata
# Delete the apt lists to save space 
RUN rm -rf /var/lib/apt/lists*

# Copy the file to working dir
COPY requirements.txt /app/requirements.txt

# Update pip (flag removes the cached packets)
RUN pip install --no-cache-dir --upgrade pip

# Install depends
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy entire project over
COPY . /app

#RUN mkdir -p

# Open the 800 port for FastAPI
EXPOSE 8000