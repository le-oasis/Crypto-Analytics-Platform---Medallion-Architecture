.PHONY: help setup build start stop restart logs clean test init-airflow init-db seed-data

# Default target
help:
	@echo "🚀 Crypto Analytics Platform - Make Commands"
	@echo ""
	@echo "Setup & Initialization:"
	@echo "  make setup          - Initial setup (creates env files, builds containers)"
	@echo "  make build          - Build all Docker containers"
	@echo "  make init-airflow   - Initialize Airflow database and create admin user"
	@echo "  make init-db        - Initialize PostgreSQL schemas and tables"
	@echo "  make seed-data      - Seed historical crypto data (1 year)"
	@echo ""
	@echo "Service Management:"
	@echo "  make start          - Start all services"
	@echo "  make stop           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make logs           - View logs from all containers"
	@echo "  make logs-airflow   - View Airflow logs"
	@echo "  make logs-streamlit - View Streamlit logs"
	@echo ""
	@echo "Development:"
	@echo "  make shell-airflow  - Open shell in Airflow container"
	@echo "  make shell-dbt      - Open shell in dbt container"
	@echo "  make dbt-run        - Run all dbt models"
	@echo "  make dbt-test       - Run dbt tests"
	@echo "  make dbt-docs       - Generate and serve dbt documentation"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test           - Run all tests"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code with black/isort"
	@echo ""
	@echo "Data Management:"
	@echo "  make trigger-bronze - Trigger bronze ingestion DAG"
	@echo "  make trigger-ml     - Trigger ML training DAG"
	@echo "  make backfill       - Backfill historical data"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          - Remove containers and volumes (destructive!)"
	@echo "  make clean-cache    - Clear Python cache files"

# Setup and Initialization
setup:
	@echo "🔧 Setting up Crypto Analytics Platform..."
	@cp -n config/secrets.env.example config/secrets.env || true
	@echo "✓ Created secrets.env (please update with your API keys)"
	@mkdir -p airflow/logs airflow/dags airflow/plugins data/mlflow data/postgres
	@echo "✓ Created necessary directories"
	@docker-compose build
	@echo "✓ Built all containers"
	@echo ""
	@echo "⚠️  IMPORTANT: Edit config/secrets.env with your API keys before starting!"
	@echo "   Then run: make init-airflow && make start"

build:
	@echo "🔨 Building Docker containers..."
	@docker-compose build

init-airflow:
	@echo "🎯 Initializing Airflow..."
	@docker-compose up -d postgres redis
	@sleep 5
	@docker-compose run --rm airflow-init
	@echo "✓ Airflow initialized (user: admin, pass: admin)"

init-db:
	@echo "🗄️  Initializing database schemas..."
	@docker-compose up -d postgres
	@sleep 3
	@docker-compose exec -T postgres psql -U airflow -d crypto_analytics < scripts/init_db.sql
	@echo "✓ Database schemas created"

seed-data:
	@echo "🌱 Seeding historical crypto data..."
	@docker-compose exec airflow-scheduler python /opt/airflow/scripts/seed_historical_data.py
	@echo "✓ Historical data seeded"

# Service Management
start:
	@echo "🚀 Starting all services..."
	@docker-compose up -d
	@echo ""
	@echo "✓ Services started!"
	@echo ""
	@echo "📊 Access the platform:"
	@echo "  • Airflow UI:        http://localhost:8080  (admin / admin)"
	@echo "  • Streamlit:         http://localhost:8501"
	@echo "  • MLflow:            http://localhost:5000"
	@echo "  • Jupyter:           http://localhost:8888"
	@echo "  • Metabase:          http://localhost:3000"
	@echo "  • MinIO Console:     http://localhost:9001  (minio / minio123)"
	@echo "  • Grafana:           http://localhost:3001  (admin / admin)"

stop:
	@echo "🛑 Stopping all services..."
	@docker-compose down

restart:
	@echo "🔄 Restarting all services..."
	@docker-compose restart

logs:
	@docker-compose logs -f

logs-airflow:
	@docker-compose logs -f airflow-scheduler airflow-webserver airflow-worker

logs-streamlit:
	@docker-compose logs -f streamlit

# Development
shell-airflow:
	@docker-compose exec airflow-scheduler bash

shell-dbt:
	@docker-compose exec dbt bash

dbt-run:
	@echo "🏃 Running dbt models..."
	@docker-compose exec dbt dbt run --profiles-dir /root/.dbt

dbt-test:
	@echo "🧪 Running dbt tests..."
	@docker-compose exec dbt dbt test --profiles-dir /root/.dbt

dbt-docs:
	@echo "📚 Generating dbt documentation..."
	@docker-compose exec dbt dbt docs generate --profiles-dir /root/.dbt
	@docker-compose exec dbt dbt docs serve --profiles-dir /root/.dbt --port 8080

# Testing
test:
	@echo "🧪 Running tests..."
	@docker-compose exec airflow-scheduler pytest /opt/airflow/tests/

lint:
	@echo "🔍 Running linters..."
	@docker-compose exec airflow-scheduler flake8 /opt/airflow/dags /opt/airflow/src
	@docker-compose exec airflow-scheduler pylint /opt/airflow/dags /opt/airflow/src

format:
	@echo "✨ Formatting code..."
	@docker-compose exec airflow-scheduler black /opt/airflow/dags /opt/airflow/src
	@docker-compose exec airflow-scheduler isort /opt/airflow/dags /opt/airflow/src

# Data Management
trigger-bronze:
	@echo "🥉 Triggering bronze ingestion DAG..."
	@docker-compose exec airflow-scheduler airflow dags trigger bronze_ingestion_dag

trigger-silver:
	@echo "🥈 Triggering silver transformation DAG..."
	@docker-compose exec airflow-scheduler airflow dags trigger silver_transformation_dag

trigger-gold:
	@echo "🥇 Triggering gold aggregation DAG..."
	@docker-compose exec airflow-scheduler airflow dags trigger gold_aggregation_dag

trigger-ml:
	@echo "🤖 Triggering ML training DAG..."
	@docker-compose exec airflow-scheduler airflow dags trigger ml_training_dag

backfill:
	@echo "⏮️  Backfilling data for last 30 days..."
	@docker-compose exec airflow-scheduler airflow dags backfill bronze_ingestion_dag \
		--start-date 2024-01-01 \
		--end-date 2024-02-01

# Database utilities
db-connect:
	@docker-compose exec postgres psql -U airflow -d crypto_analytics

db-backup:
	@echo "💾 Backing up database..."
	@docker-compose exec postgres pg_dump -U airflow crypto_analytics > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✓ Backup created: backup_$(shell date +%Y%m%d_%H%M%S).sql"

db-restore:
	@echo "📥 Restoring database from backup..."
	@read -p "Enter backup file name: " file; \
	docker-compose exec -T postgres psql -U airflow crypto_analytics < $$file

# Cleanup
clean:
	@echo "⚠️  WARNING: This will remove all containers and volumes (data will be lost)!"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		echo "✓ All containers and volumes removed"; \
	else \
		echo "Cancelled"; \
	fi

clean-cache:
	@echo "🧹 Cleaning Python cache..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✓ Cache cleaned"

# Monitoring
ps:
	@docker-compose ps

stats:
	@docker stats --no-stream

health:
	@echo "🏥 Service Health Checks:"
	@echo ""
	@echo "Postgres:"
	@docker-compose exec postgres pg_isready -U airflow || echo "❌ Down"
	@echo ""
	@echo "Redis:"
	@docker-compose exec redis redis-cli ping || echo "❌ Down"
	@echo ""
	@echo "Airflow Webserver:"
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health || echo "❌ Down"
	@echo ""
	@echo "Streamlit:"
	@curl -s -o /dev/null -w "%{http_code}" http://localhost:8501/_stcore/health || echo "❌ Down"

# Quick commands
up: start
down: stop
rebuild: clean-cache build
full-setup: setup init-airflow init-db start seed-data
	@echo ""
	@echo "🎉 Full setup complete!"
	@echo "Your crypto analytics platform is ready!"
