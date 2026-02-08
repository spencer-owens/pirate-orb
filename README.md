<p align="center">
  <img src="assets/Gemini_Generated_Image_ly72iely72iely72.png" alt="Pirate Orb Logo" width="200"/>
</p>

# Pirate Orb 🏴‍☠️

Pirate Orb is a containerized media server stack managed with Docker Compose (via OrbStack) for MacOS. It includes services for requesting, downloading, and managing movies, TV shows, and music, all tied together for a seamless automated media experience.

This is meant to be run with Plex/Jellyfin/Emby, but the actual media server was left out because of the perceived gains in transcoding performance running those servers natively rather than on containerized Linux VM. Simply point those servers to your root movie/tv/music directories.

## Services Included

### Download Clients
- **SABnzbd**: A powerful newsreader for downloading from Usenet.
- **qBittorrent**: A torrent client for P2P downloads, routed through VPN.
- **gluetun**: A VPN container that protects all torrent traffic (supports ProtonVPN, Mullvad, and others).

### Media Management
- **Prowlarr**: An indexer manager for your P2P and Usenet clients.
- **Radarr**: Manages your movie collection.
- **Sonarr**: Manages your TV show collection.
- **Lidarr**: Manages your music collection.
- **Whisparr**: Manages your adult video collection.

### Request & Access
- **Jellyseerr**: A request management and media discovery tool for your users.
- **ngrok**: Provides secure external access to Jellyseerr from anywhere.

## 1. Initial Setup

### Prerequisites

- **[OrbStack](https://orbstack.dev/)**: Used as the Docker runtime environment. You can also use Docker Desktop, but paths in the AppleScript may need adjustment.
- **Usenet Provider & Indexers**: To download via Usenet, you need an account with a Usenet provider and access to Usenet indexers (configured in Prowlarr).
- **VPN Provider** (for torrents): A VPN service compatible with gluetun (ProtonVPN, Mullvad, NordVPN, etc.) to protect torrent traffic.
- **Torrent Indexers** (optional): Access to torrent indexers/trackers for P2P downloads.

### Installation

1.  **Clone the Repository**

    ```bash
    git clone https://github.com/spencer-owens/pirate-orb.git
    cd pirate-orb
    ```

2.  **Configure Your Environment**

    This project uses an `.env` file to manage user-specific paths and settings.

    -   Copy the example template:
        ```bash
        cp .env.example .env
        ```
    -   Open the `.env` file and customize the variables:

        **System Configuration:**

        | Variable         | Description                                                                 |
        | ---------------- | --------------------------------------------------------------------------- |
        | `PUID` / `PGID`  | Your user and group ID. Run `id` in your terminal to find these values.     |
        | `TZ`             | Your timezone (e.g., `America/Chicago`).                                    |

        **Media and Download Paths:**

        | Variable         | Description                                                                 |
        | ---------------- | --------------------------------------------------------------------------- |
        | `DOWNLOADS_PATH` | Absolute path for completed downloads (staging area for both Usenet & torrents). |
        | `MOVIES_PATH`    | Absolute path to your movies library folder.                                |
        | `TV_PATH`        | Absolute path to your TV shows library folder.                              |
        | `MUSIC_PATH`     | Absolute path to your music library folder.                                 |
        | `ADULT_PATH`     | Absolute path to your adult content library folder.                         |

        **Secondary Storage Paths (Optional):**

        | Variable         | Description                                                                 |
        | ---------------- | --------------------------------------------------------------------------- |
        | `MOVIES_PATH_2`  | Secondary movies folder (e.g., on a second hard drive).                     |
        | `TV_PATH_2`      | Secondary TV shows folder.                                                  |
        | `MUSIC_PATH_2`   | Secondary music folder.                                                     |
        | `ADULT_PATH_2`   | Secondary adult content folder.                                             |

        **External Access:**

        | Variable          | Description                                                                |
        | ----------------- | -------------------------------------------------------------------------- |
        | `NGROK_AUTHTOKEN` | Your ngrok authentication token for external Jellyseerr access.            |

        **VPN Configuration (for torrent protection):**

        | Variable               | Description                                                           |
        | ---------------------- | --------------------------------------------------------------------- |
        | `WIREGUARD_PRIVATE_KEY`| Your VPN provider's WireGuard private key.                            |

    **This `.env` file is ignored by Git and will not be committed to the repository.**

## 2. Running the Stack

Once your `.env` file is configured, start the entire media stack:

```bash
# You may need to run this first if using OrbStack
orb start

# Start all services
docker compose up -d
```

The first time you run this, Docker will download all the necessary container images, which may take some time.

To stop the stack:

```bash
docker compose down
```

## 3. Updating Services

Since all services use Docker images with the `latest` tag, updating is straightforward:

```bash
# Pull the latest versions of all images
docker compose pull

# Recreate containers with the new images
docker compose up -d

# Clean up old, unused images to free disk space
docker image prune -f
```

## 4. Using the AppleScript (Optional)

For convenience, this repository includes an AppleScript that allows you to start and stop the entire stack as a standalone macOS application.

1.  **Configure the Script**
    -   Open the `pirate-orb.applescript.example` file.
    -   Change the `projectPath` to the actual path where you cloned the repository.

2.  **Save as an Application**
    -   In Script Editor, go to `File > Export`.
    -   Set the **File Format** to **Application**.
    -   Ensure **"Stay open after run handler"** is checked.
    -   Save to your Desktop or Applications folder.

## 5. Accessing Services

Once the stack is running, access each service in your web browser:

| Service | URL | Description |
|---------|-----|-------------|
| **SABnzbd** | http://localhost:8080 | Usenet downloader |
| **qBittorrent** | http://localhost:8085 | Torrent client (VPN protected) |
| **Prowlarr** | http://localhost:9696 | Indexer manager |
| **Radarr** | http://localhost:7878 | Movie management |
| **Sonarr** | http://localhost:8989 | TV show management |
| **Lidarr** | http://localhost:8686 | Music management |
| **Whisparr** | http://localhost:6969 | Adult content management |
| **Jellyseerr** | http://localhost:5055 | Request management |

### External Access via ngrok

If you've configured ngrok, Jellyseerr will be accessible from anywhere:

1. Create an ngrok account at https://ngrok.com
2. Get your authtoken from the ngrok dashboard
3. Add it to your `.env` file as `NGROK_AUTHTOKEN`
4. (Optional) Set up a static domain in the ngrok dashboard
5. Update the `command` in `docker-compose.yml` to use your domain:
   ```yaml
   command: http --url=your-domain.ngrok.app jellyseerr:5055
   ```

## 6. Post-Installation Configuration

### A. Configure SABnzbd (Usenet)

1.  Open SABnzbd at `http://localhost:8080`
2.  Complete the setup wizard with your Usenet provider details
3.  Go to `Settings > General` and note the **API Key**

### B. Configure qBittorrent (Torrents)

1.  Open qBittorrent at `http://localhost:8085`
2.  Login with `admin` and the temporary password from logs:
    ```bash
    docker logs qbittorrent 2>&1 | grep password
    ```
3.  Go to `Tools > Options > Web UI` and set a permanent password
4.  (Recommended) Increase or disable "Ban client after consecutive failures" to prevent Docker containers from being locked out

### C. Configure Prowlarr

1.  Open Prowlarr at `http://localhost:9696`
2.  Go to `Settings > Indexers` and add your Usenet and torrent indexers
3.  Note the **API Key** from `Settings > General`

### D. Configure Radarr, Sonarr, Lidarr, and Whisparr

The process is similar for all *arr applications:

1.  **Connect to Prowlarr** (indexers sync automatically):
    -   Go to `Settings > Indexers` and click `+`
    -   Select **Prowlarr**
    -   Prowlarr Server: `http://prowlarr:9696`
    -   Paste your Prowlarr API key
    -   Test and save

2.  **Connect to SABnzbd** (Usenet):
    -   Go to `Settings > Download Clients` and click `+`
    -   Select **SABnzbd**
    -   Host: `sabnzbd`
    -   API Key: Your SABnzbd API key
    -   Priority: `1` (higher priority)
    -   Test and save

3.  **Connect to qBittorrent** (Torrents):
    -   Go to `Settings > Download Clients` and click `+`
    -   Select **qBittorrent**
    -   Host: `gluetun` (NOT localhost)
    -   Port: `8085`
    -   Username: `admin`
    -   Password: Your qBittorrent password
    -   Category: `radarr` (or `sonarr`, `lidarr`, `whisparr` respectively)
    -   Priority: `50` (lower priority, used as fallback)
    -   Test and save

**Repeat for each *arr app.**

### E. Configure Jellyseerr

1.  Open Jellyseerr at `http://localhost:5055`
2.  Follow the setup wizard
3.  Connect to Radarr & Sonarr:
    -   **Radarr**: Hostname `radarr`, Port `7878`, use Radarr's API key
    -   **Sonarr**: Hostname `sonarr`, Port `8989`, use Sonarr's API key
4.  Set default root folders and quality profiles for requests

## 7. VPN Protection for Torrents

All torrent traffic is automatically routed through the VPN container (gluetun). This provides:

- **IP Protection**: Your real IP is hidden from torrent peers and trackers
- **Kill Switch**: If VPN disconnects, qBittorrent loses all network access (no leaks)
- **Selective Routing**: Only torrent traffic uses VPN; other services use normal network

### Verify VPN is Working

```bash
# Check qBittorrent's public IP (should show VPN IP, not your real IP)
docker exec qbittorrent curl -s ifconfig.me

# Check gluetun VPN status
docker logs gluetun 2>&1 | grep "Public IP"
```

### VPN Configuration

The default configuration uses ProtonVPN with WireGuard. To set up:

1. Go to your VPN provider's dashboard
2. Generate a WireGuard configuration
3. Copy the private key to your `.env` file as `WIREGUARD_PRIVATE_KEY`

For other VPN providers, see [gluetun documentation](https://github.com/qdm12/gluetun-wiki).

## 8. Multi-Drive Storage Setup

If you have multiple hard drives, configure secondary storage paths:

1. **Create matching folder structure** on your new drive:
   ```bash
   mkdir -p /Volumes/YourDrive/{Movies,TV,Music,XXX}
   ```

2. **Add secondary paths to `.env`**:
   ```bash
   MOVIES_PATH_2=/Volumes/YourDrive/Movies
   TV_PATH_2=/Volumes/YourDrive/TV
   MUSIC_PATH_2=/Volumes/YourDrive/Music
   ADULT_PATH_2=/Volumes/YourDrive/XXX
   ```

3. **Recreate the containers**:
   ```bash
   docker compose up -d --force-recreate
   ```

4. **Add root folders in each *arr app**:
   - Go to Settings → Media Management → Root Folders
   - Add the secondary path (e.g., `/movies-leviathan`)

5. **Add folders to Plex/Jellyfin/Emby**:
   - Edit each library and add the new drive paths

## 9. Download Priority

With both Usenet (SABnzbd) and Torrents (qBittorrent) configured, the *arr apps will:

1. Search ALL indexers simultaneously (both Usenet and torrent)
2. Rank results by quality, size, and your preferences
3. Select the best match and send to the appropriate download client

**Priority Settings** (configured per download client):
- Lower number = higher priority
- SABnzbd at priority `1` + qBittorrent at priority `50` = Usenet preferred, torrents as fallback
- Both at priority `1` = Best quality wins regardless of source

## Troubleshooting

### qBittorrent Authentication Failures
If *arr apps can't connect to qBittorrent, it may have banned the IP after failed attempts:
```bash
docker compose restart qbittorrent
```
Then increase "Ban client after consecutive failures" in qBittorrent settings.

### VPN Not Connecting
Check gluetun logs:
```bash
docker logs gluetun
```
Ensure your `WIREGUARD_PRIVATE_KEY` is correct in `.env`.

### Services Can't Find Each Other
Use container names (not `localhost`) for inter-service communication:
- SABnzbd: `sabnzbd:8080`
- qBittorrent: `gluetun:8085`
- Prowlarr: `prowlarr:9696`
- Radarr: `radarr:7878`
- Sonarr: `sonarr:8989`

## MusicSeerr

A lightweight music request UI that bypasses Lidarr's broken search by querying MusicBrainz directly.

### Local Access
- **URL**: http://localhost:3333

### External Access (via ngrok)
- **URL**: https://music-orb.ngrok.app

### Features
- Search artists and albums via MusicBrainz
- One-click add to Lidarr with correct MBID
- Shows existing library status
- Works around Lidarr's broken search index

### CLI Alternative
```bash
# Quick add (auto-selects first match)
./scripts/lidarr-add-quick.sh "Artist Name"

# Interactive (choose from results)
./scripts/lidarr-add.sh "Artist Name"
```

## Maintenance Scripts

| Script | Purpose |
|--------|---------|
| `scripts/health-monitor.sh` | Check all services, VPN, disk usage |
| `scripts/backup-configs.sh` | Backup all service configs |
| `scripts/lidarr-diagnostics.sh` | Debug Lidarr metadata issues |
| `scripts/lidarr-add.sh` | Interactive artist add via MusicBrainz |
| `scripts/lidarr-add-quick.sh` | Non-interactive artist add |

### Cron Setup (Optional)
```bash
# Health check every 15 min
*/15 * * * * /path/to/pirate-orb/scripts/health-monitor.sh

# Weekly backup (Sunday 3 AM)
0 3 * * 0 /path/to/pirate-orb/scripts/backup-configs.sh
```
