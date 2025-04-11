# Clean previous builds
docker-compose down
docker system prune -a

# Rebuild
docker-compose build --no-cache
docker-compose up