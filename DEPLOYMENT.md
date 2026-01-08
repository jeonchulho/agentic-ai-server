# Production Deployment Guide

This guide covers deploying Agentic AI Server to production environments.

## Prerequisites

- Linux server (Ubuntu 20.04+ recommended)
- Docker & Docker Compose installed
- Domain name (optional but recommended)
- SSL certificate (Let's Encrypt recommended)
- Sufficient resources:
  - **Minimum**: 4 CPU cores, 8GB RAM, 50GB storage
  - **Recommended**: 8 CPU cores, 16GB RAM, 100GB SSD

## Production Checklist

### Security

- [ ] Change all default passwords
- [ ] Set strong `SECRET_KEY` in environment
- [ ] Configure firewall (UFW or iptables)
- [ ] Enable SSL/TLS
- [ ] Set up rate limiting
- [ ] Configure CORS properly
- [ ] Enable authentication (implement JWT)
- [ ] Regular security updates

### Performance

- [ ] Configure resource limits
- [ ] Enable persistent volumes
- [ ] Set up load balancing (if needed)
- [ ] Configure caching strategy
- [ ] Optimize database indexes
- [ ] Enable query caching

### Monitoring

- [ ] Set up logging aggregation
- [ ] Configure health checks
- [ ] Monitor resource usage
- [ ] Set up alerting
- [ ] Track API metrics

### Backup

- [ ] Database backup strategy
- [ ] Vector database backup
- [ ] Document storage backup
- [ ] Configuration backup

## Step-by-Step Deployment

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create application user
sudo useradd -m -s /bin/bash agentic
sudo usermod -aG docker agentic
```

### 2. Application Deployment

```bash
# Switch to application user
sudo su - agentic

# Clone repository
git clone https://github.com/jeonchulho/agentic-ai-server.git
cd agentic-ai-server

# Create production environment file
cp .env.example .env.prod
nano .env.prod
```

**Production Environment Variables:**

```env
# Database - MySQL
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=agentic_user
MYSQL_PASSWORD=STRONG_PASSWORD_HERE
MYSQL_DATABASE=agentic_ai

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=STRONG_PASSWORD_HERE

# Milvus
MILVUS_HOST=milvus
MILVUS_PORT=19530

# OpenAI
OPENAI_API_KEY=your_production_key_here
LLM_MODEL=gpt-4
LLM_TEMPERATURE=0.7

# Application
DEBUG=False
LOG_LEVEL=INFO
SECRET_KEY=GENERATE_RANDOM_SECRET_KEY_HERE

# Production Settings
MAX_UPLOAD_SIZE_MB=100
MAX_WORKERS=8
```

### 3. Docker Compose Production Configuration

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_PASSWORD}
      MYSQL_DATABASE: ${MYSQL_DATABASE}
      MYSQL_USER: ${MYSQL_USER}
      MYSQL_PASSWORD: ${MYSQL_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - agentic-network
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G

  redis:
    image: redis:7-alpine
    restart: always
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    networks:
      - agentic-network
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  milvus:
    image: milvusdb/milvus:v2.3.5
    restart: always
    depends_on:
      - milvus-etcd
      - milvus-minio
    volumes:
      - milvus_data:/var/lib/milvus
    networks:
      - agentic-network
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G

  app:
    build: .
    restart: always
    env_file:
      - .env.prod
    volumes:
      - upload_data:/tmp/uploads
    networks:
      - agentic-network
    depends_on:
      - mysql
      - redis
      - milvus
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G

  nginx:
    image: nginx:alpine
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    networks:
      - agentic-network
    depends_on:
      - app

volumes:
  mysql_data:
  redis_data:
  milvus_data:
  upload_data:

networks:
  agentic-network:
    driver: bridge
```

### 4. Nginx Configuration

Create `nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream app {
        server app:8000;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        listen 80;
        server_name your-domain.com;

        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;

        # Increase upload size
        client_max_body_size 100M;

        location / {
            limit_req zone=api_limit burst=20;
            
            proxy_pass http://app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # Health check endpoint (bypass rate limiting)
        location /health {
            proxy_pass http://app;
        }
    }
}
```

### 5. SSL Certificate Setup (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Copy certificates
sudo mkdir -p ssl
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/key.pem
sudo chown -R agentic:agentic ssl/
```

### 6. Start Production Services

```bash
# Build and start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f app
```

### 7. Firewall Configuration

```bash
# Install UFW
sudo apt install ufw

# Configure firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Monitoring Setup

### 1. Application Logging

Configure centralized logging:

```bash
# Install logging driver (optional)
# Use ELK Stack, Loki, or cloud logging services
```

### 2. Health Monitoring

Set up monitoring with Prometheus + Grafana:

```yaml
# Add to docker-compose.prod.yml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
  volumes:
    - grafana_data:/var/lib/grafana
```

### 3. Uptime Monitoring

Use external services like:
- UptimeRobot
- Pingdom
- StatusCake

## Backup Strategy

### Database Backup

```bash
# MySQL backup script
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker exec agentic-mysql mysqldump -u root -p${MYSQL_PASSWORD} agentic_ai > backup_${DATE}.sql
gzip backup_${DATE}.sql
# Upload to S3 or backup server
```

### Automated Backups

Add to crontab:

```bash
# Daily backup at 2 AM
0 2 * * * /home/agentic/backup.sh
```

## Scaling Strategies

### Horizontal Scaling

1. **Load Balancer**: Use nginx or HAProxy
2. **Multiple App Instances**: Scale app service
3. **Database Replication**: MySQL master-slave
4. **Shared Storage**: Use S3 or NFS for uploads

### Vertical Scaling

Increase resources in docker-compose:

```yaml
deploy:
  resources:
    limits:
      cpus: '8'
      memory: 16G
```

## Maintenance

### Regular Updates

```bash
# Update application
cd /home/agentic/agentic-ai-server
git pull origin main
docker-compose build
docker-compose up -d

# Update system
sudo apt update && sudo apt upgrade -y

# Clean old Docker images
docker system prune -a
```

### Log Rotation

Configure log rotation to prevent disk space issues:

```bash
# /etc/logrotate.d/agentic-ai
/var/log/agentic-ai/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 agentic agentic
}
```

## Troubleshooting

### High Memory Usage

```bash
# Check memory usage
docker stats

# Restart specific service
docker-compose restart app
```

### Database Connection Issues

```bash
# Check database logs
docker-compose logs mysql

# Test connection
docker exec -it agentic-mysql mysql -u root -p
```

### Performance Issues

1. Check Redis cache hit rate
2. Monitor database query performance
3. Review application logs for errors
4. Check resource utilization

## Security Best Practices

1. **Regular Updates**: Keep all dependencies updated
2. **Principle of Least Privilege**: Limit service permissions
3. **Network Segmentation**: Use Docker networks
4. **Secrets Management**: Use Docker secrets or vault
5. **Audit Logging**: Log all important operations
6. **Regular Backups**: Test backup restoration

## Support and Resources

- **Documentation**: See main README.md
- **Issues**: GitHub Issues
- **Community**: Join our Discord/Slack
- **Professional Support**: Contact for enterprise support

---

**Remember**: Always test changes in a staging environment before applying to production!
