FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860

WORKDIR /app
RUN useradd --create-home --uid 1000 user \
    && mkdir -p /app/data \
    && chown -R user:user /app

COPY --chown=user:user requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user bot.py ./
COPY --chown=user:user photo_*.jpg ./

USER user
EXPOSE 7860
CMD ["python", "bot.py"]
