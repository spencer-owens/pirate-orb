<p align="center">
  <img src="assets/Gemini_Generated_Image_ly72iely72iely72.png" alt="Pirate Orb Logo" width="200"/>
</p>

# Pirate Orb 🏴‍☠️

Pirate Orb is a containerized media server stack managed with Docker Compose (via OrbStack) for MacOS. It includes services for requesting, downloading, and managing movies, TV shows, and music, all tied together for a seamless automated media experience. 

This is meant to be run with Plex/Jellyfin/Emby, but the actual media server was left out because of the perceived gains in transcoding performance running those servers natively rather than on containerized Linux VM. Simply point those servers to your root movie/tv/music directories. 

## Services Included

- **SABnzbd**: A powerful newsreader for downloading from Usenet.
- **Prowlarr**: An indexer manager for your P2P and Usenet clients.
- **Radarr**: Manages your movie collection.
- **Sonarr**: Manages your TV show collection.
- **Lidarr**: Manages your music collection.
- **Jellyseerr**: A request management and media discovery tool for your users.

## 1. Initial Setup

### Prerequisites

- **[OrbStack](https://orbstack.dev/)**: Used as the Docker runtime environment. You can also use Docker Desktop, but paths in the AppleScript may need adjustment.
- **Usenet Provider & Indexers**: To actually download content, you will need an account with a Usenet provider and access to Usenet indexers (which you will configure in Prowlarr). These are third-party services that typically require a subscription.

### Installation

1.  **Clone the Repository**

    Clone this repository to your local machine. A good place for it is in your user's home directory or a dedicated `projects` folder.

    ```bash
    git clone https://github.com/spencer-owens/pirate-orb.git
    cd pirate-orb
    ```

2.  **Configure Your Environment**

    This project uses an `.env` file to manage user-specific paths and settings. This keeps your personal configuration separate from the main `docker-compose.yml`.

    -   First, copy the example template:
        ```bash
        cp .env.example .env
        ```
    -   Now, open the newly created `.env` file in a text editor. You will need to customize the variables:

        | Variable         | Description                                                                                             |
        | ---------------- | ------------------------------------------------------------------------------------------------------- |
        | `PUID` / `PGID`  | Your user and group ID. Run `id` in your terminal to find these values.                                 |
        | `TZ`             | Your timezone (e.g., `America/New_York`).                                                               |
        | `DOWNLOADS_PATH` | The **absolute path** to where you want SABnzbd to store completed downloads.                           |
        | `MOVIES_PATH`    | The **absolute path** to your movies library folder.                                                    |
        | `TV_PATH`        | The **absolute path** to your TV shows library folder.                                                  |
        | `MUSIC_PATH`     | The **absolute path** to your music library folder.                                                     |

    **This `.env` file is ignored by Git and will not be committed to the repository.**

## 2. Running the Stack

Once your `.env` file is configured, you can start the entire media stack with a single command:

(you may need to run ```orb start``` first)

```bash
docker compose up -d
```

The first time you run this, Docker will download all the necessary container images, which may take some time. On subsequent runs, it will be much faster.

To stop the stack:

```bash
docker compose down
```

## 3. Using the AppleScript (Optional)

For convenience, this repository includes an AppleScript that allows you to start and stop the entire stack as a standalone macOS application.

1.  **Configure the Script**
    -   Open the `pirate-orb.applescript.example` file.
    -   Find the line `set projectPath to "/path/to/your/pirate-orb"` and change the placeholder path to the actual, absolute path where you cloned the repository.
    -   The script assumes you are using OrbStack. If you use Docker Desktop, you may need to find the location of your `docker` executable and update the `dockerPath` variable.

2.  **Save as an Application**
    -   In Script Editor, go to `File > Export`.
    -   Set the **File Format** to **Application**.
    -   Ensure the **"Stay open after run handler"** checkbox is checked.
    -   Save the application to your Desktop or Applications folder.

Now you can double-click the app to start your media server stack and quit it from the Dock (`Right-click > Quit`) to shut it down.

## 4. Accessing Services

Once the stack is running, you can access each service in your web browser at the following local addresses:

-   **SABnzbd**: http://localhost:8080
-   **Prowlarr**: http://localhost:9696
-   **Radarr**: http://localhost:7878
-   **Sonarr**: http://localhost:8989
-   **Lidarr**: http://localhost:8686
-   **Jellyseerr**: http://localhost:5055

You will need to go through the initial setup wizard for each of these applications the first time you launch them.

## 5. Post-Installation Configuration

Getting the services running is the first step. To make them work together as an automated system, you need to configure them to communicate with each other. This usually involves copying API keys from one service and pasting them into another.

Here is a general workflow to follow:

### A. Configure SABnzbd

1.  Open SABnzbd at `http://localhost:8080`.
2.  On first launch, it will run a setup wizard.
3.  When prompted, enter the server details for your Usenet provider (e.g., server address, port, username, password).
4.  Complete the wizard.
5.  After the setup, go to `Settings (cog icon) > General` and find the **API Key**. You will need this key later.

### B. Configure Prowlarr

1.  Open Prowlarr at `http://localhost:9696`.
2.  Go to `Settings > Indexers` and click the `+` to add your Usenet indexers.
3.  Go to `Settings > General` to find the **API Key** for Prowlarr.

### C. Configure Radarr, Sonarr, and Lidarr

The process is nearly identical for all three "*arr*" applications. I'll use Radarr as the main example.

1.  **Connect to Prowlarr**:
    -   Open Radarr at `http://localhost:7878`.
    -   Go to `Settings > Indexers` and click `+`.
    -   Select **Prowlarr**.
    -   For the `Prowlarr Server` URL, enter `http://prowlarr:9696`. We use the container name `prowlarr` here because the services are on the same Docker network.
    -   Paste the Prowlarr API key you copied earlier.
    -   Test and save. Your indexers from Prowlarr should now be available in Radarr.

2.  **Connect to SABnzbd**:
    -   In Radarr, go to `Settings > Download Clients` and click `+`.
    -   Select **SABnzbd**.
    -   For the `Host`, enter `sabnzbd`.
    -   For the `API Key`, paste the SABnzbd API key you copied from its settings.
    -   Test and save. Radarr can now send download requests to SABnzbd.

**Repeat these two steps for Sonarr (`http://localhost:8989`) and Lidarr (`http://localhost:8686`).**

### D. Configure Jellyseerr

1.  Open Jellyseerr at `http://localhost:5055`.
2.  Follow the setup wizard.
3.  When prompted to connect to Radarr & Sonarr:
    -   **Radarr**:
        -   Hostname: `radarr`
        -   Port: `7878`
        -   API Key: Go to Radarr's settings (`Settings > General`) to find its API key.
    -   **Sonarr**:
        -   Hostname: `sonarr`
        -   Port: `8989`
        -   API Key: Go to Sonarr's settings (`Settings > General`) to find its API key.
4.  Complete the setup. Jellyseerr can now process media requests and send them to the correct service.
