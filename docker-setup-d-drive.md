# Configure Docker Desktop to Use D: Drive

## Windows Docker Desktop Settings:

1. **Open Docker Desktop**
2. **Go to Settings → Resources → Advanced**
3. **Change Disk Image Location:**
   - Default: `C:\Users\%USERNAME%\AppData\Local\Docker\wsl`
   - Change to: `D:\Docker\wsl`

4. **WSL2 Backend Configuration:**
   Create/edit `%USERPROFILE%\.wslconfig`:
   ```
   [wsl2]
   memory=8GB
   processors=4
   swap=2GB
   localhostForwarding=true
   kernel=D:\\Docker\\kernel
   ```

5. **Move Docker Data:**
   ```powershell
   # Stop Docker Desktop
   wsl --shutdown
   
   # Export current distros
   wsl --export docker-desktop D:\Docker\docker-desktop.tar
   wsl --export docker-desktop-data D:\Docker\docker-desktop-data.tar
   
   # Unregister old locations
   wsl --unregister docker-desktop
   wsl --unregister docker-desktop-data
   
   # Import to D: drive
   wsl --import docker-desktop D:\Docker\distro D:\Docker\docker-desktop.tar
   wsl --import docker-desktop-data D:\Docker\data D:\Docker\docker-desktop-data.tar
   
   # Clean up exports
   del D:\Docker\*.tar
   ```

6. **Restart Docker Desktop**

## Build and Run on D: Drive:

```powershell
# Set Docker context to D: drive workspace
cd D:\AI\Neuron-AI

# Build the production image
docker build -t neuron-ai:prod --target runtime .

# Run with volume mounted from D:
docker run -d `
  --name neuron-prod `
  -p 8000:8000 `
  -p 3000:3000 `
  -p 9090:9090 `
  -v D:\AI\Neuron-AI\data:/app/data `
  -v D:\AI\Neuron-AI\logs:/app/logs `
  -e PREDICT_API_KEY=your-api-key `
  -e PROMETHEUS_URL=http://localhost:9090 `
  -e GRAFANA_BASE_URL=http://localhost:3000 `
  -e ALLOW_PARTIAL_READINESS=1 `
  neuron-ai:prod
```

## Docker Compose with D: Drive Volumes:

```yaml
version: '3.9'

services:
  app:
    build: .
    volumes:
      - D:/AI/Neuron-AI/data:/app/data
      - D:/AI/Neuron-AI/logs:/app/logs
      - D:/AI/Neuron-AI/artifacts:/app/artifacts
    environment:
      - DOCKER_DATA_ROOT=D:/Docker
    ports:
      - "8000:8000"

  prometheus:
    image: prom/prometheus
    volumes:
      - D:/AI/Neuron-AI/prometheus-data:/prometheus
      - ./monitoring/prometheus:/etc/prometheus
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    volumes:
      - D:/AI/Neuron-AI/grafana-data:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana
    ports:
      - "3000:3000"
```