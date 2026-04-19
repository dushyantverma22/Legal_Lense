# Makefile
# Usage: make build | make up | make test | make logs | make shell

.PHONY: build up down test logs shell clean ps

# Build the Docker image (uses layer cache — fast on second run)
build:
	docker compose build

# Start the API in the background
up:
	docker compose up -d api

# Start the API and tail logs in foreground (useful for debugging)
dev:
	docker compose up api

# Stop all services
down:
	docker compose down

# Run the full test suite inside Docker
test:
	docker compose run --rm test

# Run only unit tests (fastest — no API keys needed)
test-unit:
	docker compose run --rm test pytest tests/unit/ -v --tb=short

# Tail live logs from the API container
logs:
	docker compose logs -f api

# Open a bash shell inside the running API container
# Useful for: inspecting the filesystem, running one-off Python scripts
shell:
	docker compose exec api bash

# Check which containers are running
ps:
	docker compose ps

# Remove stopped containers, unused images, and volumes (WARNING: deletes data!)
clean:
	docker compose down -v
	docker system prune -f

# Build fresh image with no cache (useful when requirements.txt changes)
rebuild:
	docker compose build --no-cache

# In Makefile, add:
deploy:
	./infrastructure/deploy.sh