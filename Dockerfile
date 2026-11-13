# Avoflare server image. Build from the mineareana/ folder:  docker build -t avoflare .
FROM python:3.11-slim
WORKDIR /app
COPY avoflare/requirements.txt avoflare/requirements.txt
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r avoflare/requirements.txt
# read-only project inputs used at runtime
COPY 02_patient_data 02_patient_data
COPY 04_simulation/04_simulation/bidmc_analysis 04_simulation/04_simulation/bidmc_analysis
COPY 07_dashboard/assets 07_dashboard/assets
COPY MineArena_V4_1_Integration_Update MineArena_V4_1_Integration_Update
# application, simulated data and trained models (state/ is a volume, never baked into the image)
COPY avoflare/*.py avoflare/care_teams.json avoflare/requirements.txt avoflare/
COPY avoflare/web avoflare/web
COPY avoflare/data avoflare/data
COPY avoflare/model avoflare/model
COPY avoflare/results/*.json avoflare/results/
WORKDIR /app/avoflare
VOLUME ["/app/avoflare/state"]
EXPOSE 8000
ENV SPEED=10 URGENT_TIMEOUT=30 REVIEW_TIMEOUT=90
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
