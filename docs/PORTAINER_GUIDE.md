# Portainer Installation Guide 🐳

Complete guide for deploying Peacock TV Scraper using Portainer.

## 📋 Prerequisites

- Portainer installed and running
- Access to Portainer web interface
- Docker host with internet access
- Your Docker host IP address

## 🚀 Method 1: Using Stacks (Recommended)

This is the easiest method and allows for easy updates.

### Step-by-Step

1. **Login to Portainer**
   - Navigate to your Portainer URL (usually `http://your-server:9000`)

2. **Go to Stacks**
   - Click **Stacks** in the left sidebar
   - Click **+ Add stack** button

3. **Configure Stack**
   - **Name:** `peacock-scraper`
   - **Build method:** Web editor

4. **Paste Docker Compose Configuration**

```yaml
version: '3.8'

services:
  peacock:
    image: peacock-scraper:latest
    build:
      context: https://github.com/kineticman/PeacockDeepLinks.git
    container_name: peacock-scraper
    restart: unless-stopped
    ports:
      - "6655:6655"
    volumes:
      - peacock-data:/data
    environment:
      # IMPORTANT: Change this to your Docker host's IP address
      - PEACOCK_SERVER_HOST=192.168.86.72
      
      # Server configuration
      - PEACOCK_PORT=6655
      
      # File paths
      - PEACOCK_DB_PATH=/data/peacock_events.db
      - PEACOCK_LANES_XML_PATH=/data/peacock_lanes.xml
      - PEACOCK_LANES_M3U_PATH=/data/peacock_lanes.m3u
      - PEACOCK_CHROME_M3U_PATH=/data/peacock_lanes_chrome.m3u
      - PEACOCK_DIRECT_XML_PATH=/data/peacock_direct.xml
      - PEACOCK_DIRECT_M3U_PATH=/data/peacock_direct.m3u
      
      # Scraper configuration
      - PEACOCK_LANES=10
      - PEACOCK_DAYS_AHEAD=7
      - PEACOCK_PADDING_MINUTES=45
      - PEACOCK_LANE_START_CH=9000
      
      # API configuration
      - PEACOCK_SLUG=/sports/live-and-upcoming
      
      # Schedule (3:15 AM daily)
      - PEACOCK_REFRESH_CRON=15 3 * * *
      
      # Timezone
      - TZ=UTC
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:6655/api/status')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  peacock-data:
```

5. **Customize Environment Variables**

   **⚠️ IMPORTANT - Change these:**
   ```yaml
   - PEACOCK_SERVER_HOST=192.168.86.72    # YOUR DOCKER HOST IP
   ```

   **Optional customizations:**
   ```yaml
   - PEACOCK_LANES=20                     # More channels
   - PEACOCK_REFRESH_CRON=0 */4 * * *     # Every 4 hours
   - PEACOCK_LANE_START_CH=5000           # Different channel numbers
   ```

6. **Deploy the Stack**
   - Scroll down and click **Deploy the stack**
   - Wait for deployment to complete

7. **Verify Deployment**
   - Go to **Containers** in Portainer
   - Find `peacock-scraper` container
   - Click on it to view details
   - Click **Logs** tab
   - Look for: `Starting web server on port 6655...`

8. **Access Dashboard**
   ```
   http://YOUR_SERVER_IP:6655
   ```

---

## 🔧 Method 2: Manual Container Creation

If you prefer more control or can't use stacks.

### Step 1: Build the Image (First Time Only)

1. **Navigate to Images**
   - Click **Images** in the left sidebar
   - Click **+ Build a new image**

2. **Build from GitHub**
   - **Build method:** Git repository
   - **Repository URL:** `https://github.com/kineticman/PeacockDeepLinks`
   - **Git reference:** `main` (or your branch name)
   - **Image name:** `peacock-scraper:latest`

3. **Start Build**
   - Click **Build the image**
   - Wait for build to complete (2-5 minutes)
   - You'll see build logs streaming

4. **Verify Image**
   - Image should appear in your images list
   - Tag should be `peacock-scraper:latest`

### Step 2: Create the Container

1. **Navigate to Containers**
   - Click **Containers** in the left sidebar
   - Click **+ Add container**

2. **Basic Settings**
   ```
   Name: peacock-scraper
   Image: peacock-scraper:latest
   ```

3. **Network Ports Configuration**
   
   Click **Publish a new network port**
   ```
   Host: 6655
   Container: 6655
   Protocol: TCP
   ```

4. **Volumes Configuration**
   
   Click **Map additional volume**
   
   **Option A - Bind mount:**
   ```
   Container: /data
   Host: /path/to/peacock-data  (e.g., /opt/peacock-data)
   ```
   
   **Option B - Named volume (recommended):**
   ```
   Container: /data
   Volume: peacock-data
   ```

5. **Environment Variables**
   
   Scroll to **Advanced container settings** → **Env** tab
   
   Click **+ add environment variable** for each:

   ```
   Name                          Value
   ────────────────────────────  ──────────────────────────
   PEACOCK_SERVER_HOST           192.168.86.72
   PEACOCK_PORT                  6655
   PEACOCK_DB_PATH               /data/peacock_events.db
   PEACOCK_LANES_XML_PATH        /data/peacock_lanes.xml
   PEACOCK_LANES_M3U_PATH        /data/peacock_lanes.m3u
   PEACOCK_CHROME_M3U_PATH       /data/peacock_lanes_chrome.m3u
   PEACOCK_DIRECT_XML_PATH       /data/peacock_direct.xml
   PEACOCK_DIRECT_M3U_PATH       /data/peacock_direct.m3u
   PEACOCK_LANES                 10
   PEACOCK_DAYS_AHEAD            7
   PEACOCK_PADDING_MINUTES       45
   PEACOCK_LANE_START_CH         9000
   PEACOCK_SLUG                  /sports/live-and-upcoming
   PEACOCK_REFRESH_CRON          15 3 * * *
   TZ                            UTC
   ```

6. **Restart Policy**
   
   Go to **Restart policy** tab
   - Select: **Unless stopped**

7. **Deploy Container**
   
   Click **Deploy the container**

8. **Verify**
   
   - Container should start automatically
   - Check logs for successful startup
   - Access dashboard at `http://YOUR_IP:6655`

---

## 📱 Using Portainer Mobile App

You can also manage the container from the Portainer mobile app!

1. Install Portainer app (iOS/Android)
2. Connect to your Portainer instance
3. Navigate to your stack/container
4. View logs, restart, or modify settings
5. Trigger manual refresh via API:
   - Use a mobile browser
   - Navigate to: `http://YOUR_IP:6655/api/refresh`

---

## 🔄 Updating the Container

### For Stack Deployment

1. Go to **Stacks** → `peacock-scraper`
2. Click **Editor**
3. Modify the configuration
4. Click **Update the stack**
5. Enable **Re-pull image and redeploy**
6. Click **Update**

### For Manual Container

1. **Stop the container:**
   - Go to **Containers**
   - Select `peacock-scraper`
   - Click **Stop**

2. **Remove the container:**
   - Click **Remove**
   - Confirm removal

3. **Rebuild the image:**
   - Go to **Images**
   - Find `peacock-scraper:latest`
   - Click **Build**
   - Or delete and rebuild from Git

4. **Recreate the container:**
   - Follow Step 2 instructions again
   - Same settings, new image

---

## 🐛 Troubleshooting in Portainer

### Check Container Status

1. **Go to Containers**
2. Look for `peacock-scraper`
3. Status should be: **Running** (green)

### View Logs

1. Click on container name
2. Click **Logs** tab
3. Look for errors or startup messages
4. Should see: `Starting web server on port 6655...`

### Common Issues

#### Container won't start

**Check logs:**
```
Look for: Error, Failed, or Exception messages
```

**Solution:**
- Verify all environment variables are set
- Check port 6655 isn't already in use
- Ensure volume is properly mounted

#### Port already in use

**Check what's using port 6655:**
1. Go to container **Console**
2. Run: `netstat -tulpn | grep 6655`

**Solution:**
- Change `PEACOCK_PORT` to different port (e.g., 6656)
- Update port mapping: `6656:6656`

#### Can't access dashboard

**Check network:**
1. Verify container is running
2. Check firewall rules on host
3. Try accessing from host first: `http://localhost:6655`

**Solution:**
- Add firewall rule for port 6655
- Verify `PEACOCK_SERVER_HOST` is correct

#### M3U shows localhost

**Problem:** Didn't set server host IP

**Solution:**
1. Edit container environment variables
2. Set `PEACOCK_SERVER_HOST` to actual IP
3. Restart container
4. Trigger manual refresh

### Restart Container

**Via Portainer:**
1. Select container
2. Click **Restart**
3. Wait for green status

**Via API (from any browser):**
```
http://YOUR_IP:6655/api/refresh
```

### View Container Stats

1. Click on container
2. Click **Stats** tab
3. Monitor CPU, memory, network usage

---

## 💾 Backup and Restore

### Backup Data

**From Portainer:**
1. Click on container
2. Note the volume location
3. Use **Volumes** → `peacock-data`
4. Download files manually

**Via Host:**
```bash
# Find volume location
docker volume inspect peacock-data

# Copy data
cp -r /var/lib/docker/volumes/peacock-data/_data /backup/
```

### Restore Data

1. Stop container in Portainer
2. Replace volume data
3. Start container
4. Verify at dashboard

---

## 📊 Monitoring

### Check Refresh Status

**Via Dashboard:**
```
http://YOUR_IP:6655
```
Shows last refresh time and status

**Via API:**
```bash
curl http://YOUR_IP:6655/api/status | jq
```

### View Generated Files

1. Go to **Volumes** → `peacock-data`
2. Click **Browse**
3. See all generated files:
   - `peacock_events.db`
   - `peacock_lanes.xml`
   - `peacock_lanes.m3u`
   - `peacock_lanes_chrome.m3u`
   - `peacock_direct.xml`
   - `peacock_direct.m3u`

---

## 🎯 Quick Reference

### Essential Portainer Actions

| Action | Steps |
|--------|-------|
| **View Logs** | Containers → peacock-scraper → Logs |
| **Restart** | Containers → peacock-scraper → Restart |
| **Update Env Vars** | Containers → peacock-scraper → Duplicate/Edit |
| **Trigger Refresh** | Browser: `http://IP:6655/api/refresh` |
| **Check Status** | Browser: `http://IP:6655/api/status` |
| **View Files** | Volumes → peacock-data → Browse |

### Environment Variables to Customize

```
PEACOCK_SERVER_HOST       Your Docker host IP (REQUIRED!)
PEACOCK_PORT              Web server port (default: 6655)
PEACOCK_LANES             Number of channels (default: 10)
PEACOCK_REFRESH_CRON      Schedule (default: 15 3 * * *)
PEACOCK_LANE_START_CH     Channel start number (default: 9000)
```

---

## ✅ Post-Installation Checklist

After deploying via Portainer:

- [ ] Container status is **Running** (green)
- [ ] Logs show "Starting web server on port 6655..."
- [ ] Dashboard accessible at `http://YOUR_IP:6655`
- [ ] First refresh completed (check dashboard)
- [ ] Files generated in volume (check Volumes → Browse)
- [ ] M3U shows correct IP (not localhost)
- [ ] Can download XMLTV/M3U files
- [ ] API endpoints respond

---

## 🆘 Getting Help

If you encounter issues:

1. **Check container logs** in Portainer
2. **View API status:** `http://YOUR_IP:6655/api/status`
3. **Try manual refresh:** POST to `/api/refresh`
4. **Verify environment variables** are all set
5. **Check volume permissions**
6. **Review this guide** for common solutions

---

That's it! You should now have Peacock TV Scraper running in Portainer. 🎉
