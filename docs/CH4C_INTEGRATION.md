# Channels-4-Chrome (CH4C) Integration 🌐

## What is CH4C?

Channels-4-Chrome (CH4C) is a bridge application that allows Channels DVR to play HTTP-based streams through a Chrome browser instance. This is useful when deeplinks require browser-based authentication or special handling.

## When to Use CH4C

**Use CH4C if:**
- ✅ You want to use HTTP-based playlists instead of deeplinks
- ✅ You need browser-based authentication for Peacock
- ✅ You prefer Chrome Capture method but need Channels DVR integration
- ✅ Deeplinks aren't working reliably with your setup

**Don't use CH4C if:**
- ❌ Direct deeplinks work fine for you
- ❌ You're using ADBTuner (it has its own deeplink handling)
- ❌ You don't have CH4C installed

## Configuration

### Environment Variables

Add these to your `.env` file or docker-compose:

```bash
# CH4C server IP address
CH4C_HOST=192.168.86.72

# CH4C server port (default is 2442)
CH4C_PORT=2442
```

### Docker Compose Example

```yaml
environment:
  - PEACOCK_SERVER_HOST=192.168.86.72
  - PEACOCK_PORT=6655
  - CH4C_HOST=192.168.86.72      # Your CH4C server IP
  - CH4C_PORT=2442                # CH4C port
```

## How It Works

When CH4C variables are configured:

1. **Without CH4C** (default):
   ```m3u
   chrome://https://www.peacocktv.com/deeplink?...
   ```

2. **With CH4C** (when variables set):
   ```m3u
   http://192.168.86.72:2442/stream?url=https://www.peacocktv.com/deeplink?...
   ```

The CH4C bridge receives the HTTP request and opens the deeplink in Chrome, then streams it back to Channels DVR.

## Setup Steps

### 1. Install CH4C

Follow the CH4C installation guide for your platform:
- Download from CH4C repository
- Install Chrome browser
- Configure CH4C service

### 2. Configure Environment

**Option A - Edit .env:**
```bash
nano .env

# Add these lines:
CH4C_HOST=192.168.86.72
CH4C_PORT=2442
```

**Option B - Docker Compose:**
```yaml
environment:
  - CH4C_HOST=${CH4C_HOST:-127.0.0.1}
  - CH4C_PORT=${CH4C_PORT:-2442}
```

### 3. Restart Container

```bash
docker-compose down
docker-compose up -d
```

### 4. Verify Configuration

Check the logs:
```bash
docker-compose logs | grep CH4C
```

Check generated M3U:
```bash
curl http://localhost:6655/chrome/m3u | head -10
```

Should see URLs like:
```
http://192.168.86.72:2442/stream?url=https://...
```

## M3U Generation Logic

The application checks for CH4C configuration:

```python
ch4c_host = os.getenv("CH4C_HOST")
ch4c_port = os.getenv("CH4C_PORT", "2442")

if ch4c_host:
    # Generate CH4C bridge URLs
    stream_url = f"http://{ch4c_host}:{ch4c_port}/stream?url={deeplink}"
else:
    # Generate direct chrome:// URLs
    stream_url = f"chrome://{deeplink}"
```

## Integration with Channels DVR

### Without CH4C
```
M3U: http://192.168.86.72:6655/chrome/m3u
```
Uses `chrome://` URLs (requires Chrome Capture)

### With CH4C
```
M3U: http://192.168.86.72:6655/chrome/m3u
```
Uses `http://` URLs via CH4C bridge

## Troubleshooting

### CH4C not responding

**Check CH4C is running:**
```bash
curl http://192.168.86.72:2442/status
```

**Check configuration:**
```bash
docker-compose exec peacock env | grep CH4C
```

### Wrong URLs in M3U

**Verify environment variables are set:**
```bash
curl http://localhost:6655/api/status | jq '.config'
```

Should show CH4C settings if configured.

**Trigger refresh to regenerate M3U:**
```bash
curl -X POST http://localhost:6655/api/refresh
```

### Streams not playing

**Check CH4C logs:**
- Look for connection errors
- Verify Chrome is launching
- Check Peacock authentication

**Test deeplink directly:**
```bash
# Get deeplink
curl http://localhost:6655/api/lane/1/deeplink?format=text

# Test in CH4C
curl "http://192.168.86.72:2442/stream?url=DEEPLINK_HERE"
```

## Default Behavior

If CH4C environment variables are **not set**:
- Uses direct `chrome://` URLs
- No HTTP bridge
- Works with Chrome Capture method

If CH4C environment variables **are set**:
- Uses `http://CH4C_HOST:CH4C_PORT/stream?url=...`
- Routes through CH4C bridge
- Works with Channels DVR HTTP sources

## Example Configurations

### Local CH4C (same machine)
```bash
CH4C_HOST=127.0.0.1
CH4C_PORT=2442
```

### Remote CH4C (different machine)
```bash
CH4C_HOST=192.168.86.100
CH4C_PORT=2442
```

### Custom CH4C Port
```bash
CH4C_HOST=192.168.86.72
CH4C_PORT=3000
```

## Testing

### Test CH4C is working
```bash
# Get a deeplink
DEEPLINK=$(curl -s http://localhost:6655/api/lane/1/deeplink?format=text)

# Test through CH4C
curl -I "http://192.168.86.72:2442/stream?url=$DEEPLINK"
```

Should return HTTP 200 and start streaming.

### Compare M3U files

**Without CH4C:**
```bash
curl http://localhost:6655/chrome/m3u | head -5
# chrome://https://www.peacocktv.com/deeplink?...
```

**With CH4C:**
```bash
curl http://localhost:6655/chrome/m3u | head -5
# http://192.168.86.72:2442/stream?url=https://...
```

## Summary

- **Optional Feature** - Only configure if you need CH4C
- **Default**: Direct `chrome://` URLs
- **With CH4C**: HTTP bridge URLs
- **Automatic Detection** - Set env vars and it works
- **No Code Changes** - Just environment configuration

---

**Note:** This integration is designed to be completely optional. If you don't need CH4C, simply don't set the environment variables and the system works with direct Chrome Capture URLs.
