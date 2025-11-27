# Chrome Capture M3U Support 🌐

## What's New

Added a **third M3U file** specifically for Chrome Capture integration that uses `chrome://` URLs instead of API endpoints.

## Files Generated

1. **peacock_lanes.xml** - XMLTV guide (shared with ADBTuner)
2. **peacock_lanes.m3u** - For ADBTuner (API URLs)
3. **peacock_lanes_chrome.m3u** - For Chrome Capture (deeplink URLs) ⭐ NEW

## Chrome Capture M3U Format

**peacock_lanes_chrome.m3u** contains:

```m3u
#EXTM3U

#EXTINF:-1 tvg-id="peacock.lane.1" tvg-name="Peacock Sports 1" tvg-chno="9000" group-title="Peacock Lanes" tvg-logo="",Peacock Sports 1
chrome://https://www.peacocktv.com/deeplink?deeplinkData=%7B%22pvid%22%3A%22...%22%7D

#EXTINF:-1 tvg-id="peacock.lane.2" tvg-name="Peacock Sports 2" tvg-chno="9001" group-title="Peacock Lanes" tvg-logo="",Peacock Sports 2
chrome://https://www.peacocktv.com/deeplink?deeplinkData=%7B%22pvid%22%3A%22...%22%7D
```

## Comparison

| Feature | ADBTuner M3U | Chrome Capture M3U |
|---------|--------------|---------------------|
| **URL Format** | `http://server:6655/api/lane/1/deeplink` | `chrome://https://www.peacocktv.com/deeplink?...` |
| **Dynamic** | Yes (API call) | No (static deeplink) |
| **XMLTV** | peacock_lanes.xml | peacock_lanes.xml (same) |
| **Use Case** | ADBTuner with API | Chrome Capture integration |

## Access URLs

**Dashboard**: http://localhost:6655/

**Downloads**:
- **XMLTV**: http://localhost:6655/lanes/xmltv
- **ADBTuner M3U**: http://localhost:6655/lanes/m3u
- **Chrome Capture M3U**: http://localhost:6655/chrome/m3u ⭐

## How It Works

The Chrome Capture M3U is generated at the same time as the ADBTuner M3U, but instead of using API endpoints, it:

1. Looks up the current/upcoming event for each lane
2. Generates the Peacock deeplink for that event
3. Wraps it in `chrome://` format
4. Writes it directly to the M3U

**Important**: The deeplinks are static (generated at refresh time), so they point to whatever event is current/upcoming when the refresh runs. Unlike the ADBTuner M3U which dynamically fetches the current event via API.

## Setup for Chrome Capture

```bash
# In Channels DVR or your media server
M3U Source: http://192.168.86.72:6655/chrome/m3u
XMLTV Source: http://192.168.86.72:6655/lanes/xmltv
```

## Rebuild to Get Chrome M3U

```bash
cd ~/Projects/PeacockDeepLinks

# Download updated files:
# - peacock_server.py
# - peacock_export_hybrid.py
# - docker-compose.yml

docker-compose down
docker-compose build
docker-compose up -d

# Verify
curl http://localhost:6655/chrome/m3u | head -20
```

## Example Output

```m3u
#EXTM3U

#EXTINF:-1 tvg-id="peacock.lane.1" tvg-name="Peacock Sports 1" tvg-chno="9000" group-title="Peacock Lanes" tvg-logo="",Peacock Sports 1
chrome://https://www.peacocktv.com/deeplink?deeplinkData=%7B%22pvid%22%3A%2285b3caea-da53-3f93-b23f-e47b342ee58b%22%2C%22type%22%3A%22PROGRAMME%22%2C%22action%22%3A%22PLAY%22%7D

#EXTINF:-1 tvg-id="peacock.lane.2" tvg-name="Peacock Sports 2" tvg-chno="9001" group-title="Peacock Lanes" tvg-logo="",Peacock Sports 2
chrome://https://www.peacocktv.com/deeplink?deeplinkData=%7B%22pvid%22%3A%22a1b2c3d4-e5f6-7890-abcd-ef1234567890%22%2C%22type%22%3A%22PROGRAMME%22%2C%22action%22%3A%22PLAY%22%7D
```

## When to Use Each M3U

**Use ADBTuner M3U (`/lanes/m3u`)** when:
- ✅ Using ADBTuner
- ✅ Need dynamic deeplinks (current event changes automatically)
- ✅ Have API server running

**Use Chrome Capture M3U (`/chrome/m3u`)** when:
- ✅ Using Chrome Capture
- ✅ Want direct deeplink URLs
- ✅ Don't need dynamic updates (refresh regenerates)

## Test

```bash
# Get Chrome Capture M3U
curl http://localhost:6655/chrome/m3u

# Should see chrome:// URLs
# chrome://https://www.peacocktv.com/deeplink?...

# Compare with ADBTuner M3U
curl http://localhost:6655/lanes/m3u

# Should see API URLs
# http://192.168.86.72:6655/api/lane/1/deeplink
```

That's it! You now have a Chrome Capture-specific M3U. 🎉
