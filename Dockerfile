# Set up
FROM python:3.10-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip --no-cache-dir && \
    pip install -r requirements.txt --no-cache-dir

# Update code
COPY src/ /app/src
COPY *_Homepage.py "/app/🏠_Homepage.py"
COPY pages/01_*_Habits.py "/app/pages/01_🎯_Habits.py"
COPY pages/02_*_Productivity.py "/app/pages/02_📈_Productivity.py"
COPY pages/03_*_Planning.py "/app/pages/03_📝_Planning.py"

# Entrypoint
EXPOSE 8080
ENTRYPOINT ["streamlit", "run", "🏠_Homepage.py", "--server.port", "8080"]
