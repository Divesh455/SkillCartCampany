FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY seed.py .
COPY main.py .
COPY schema.sql .
COPY start.sh .
COPY data/jobs_150.json /app/data/jobs_150.json

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
