FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ /app/
COPY database/ /app/database/

RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]

