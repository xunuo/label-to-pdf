# Login to Azure
az login

# Create resource group
az group create --name bidockerapp-dev --location westeurope 

# 2. Create a Container App Environment
az containerapp env create --name bidockerapp-dev-env --resource-group bidockerapp-dev --location westeurope

# 3. Deploy the Flask App
# Load secrets from .env file
source .env

az containerapp create --name bidockerapp-dev-app --resource-group bidockerapp-dev --environment bidockerapp-dev-env --image philipwang/flask-app:latest --target-port 5000 --ingress external --env-vars REDIS_HOST=$REDIS_HOST REDIS_PASSWORD=$REDIS_PASSWORD
az containerapp update --name bidockerapp-dev-app --resource-group bidockerapp-dev --image philipwang/flask-app:latest 

# 4. Deploy the Celery Worker
az containerapp create --name bidockerapp-dev-celery --resource-group bidockerapp-dev --environment bidockerapp-dev-env --image philipwang/flask-celery:latest --command "celery -A tasks worker --loglevel=info" --env-vars REDIS_HOST=$REDIS_HOST REDIS_PASSWORD=$REDIS_PASSWORD REDIS_URL="rediss://:$REDIS_PASSWORD@$REDIS_HOST:6380/0?ssl_cert_reqs=none"

# After deployment, retrieve the URL of your Flask app:
az containerapp show --name bidockerapp-dev-app --resource-group bidockerapp-dev --query properties.configuration.ingress.fqdn

az containerapp logs show --name bidockerapp-dev-app --resource-group bidockerapp-dev --output table

# local run using Azure Redis Cache:
docker run -p 5000:5000 -e REDIS_HOST=$REDIS_HOST -e REDIS_PASSWORD=$REDIS_PASSWORD philipwang/flask-app:latest
docker run -p 5000:5000 -e REDIS_HOST=bidockerapp-dev-azurecacheredis.redis.cache.windows.net -e REDIS_PASSWORD=$REDIS_PASSWORDphilipwang/flask-app:latest
az containerapp ingress show --name bidockerapp-dev-app --resource-group bidockerapp-dev --query "[targetPort, external]"

docker build -t philipwang/flask-app:latest .  
docker push philipwang/flask-app:latest