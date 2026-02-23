FROM python:3.13-alpine3.21

ENV PYTHONUNBUFFERED 1
WORKDIR /app
RUN mkdir src
RUN python -m venv venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY ./src ./src
EXPOSE 5000

CMD ["flask", "--app", "./src/main.py", "run", "--host=0.0.0.0"]
