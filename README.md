# Osint Report Engine

You should only run this application locally or on a trusted, secure network. **It MUST NOT be exposed to the public internet.**

### Support
This is open source and free. Do not contact me if you can't get it working, I don't have time to provide support for this. Review the code, and open a PR. I do not provide support. Use at your own risk, no warranty

## Osint Report Engine
Osint Report Engine is a web application designed to streamline OSINT research task management, subject and findings tracking, and automated report generation.

It provides a centralized dashboard to track clients, manage tasks across various domain categories (e.g., Corporate Governance, Infrastructure, Dark Web), maintain a global risk library, and automatically generate professional, well-formatted PDF reports and Attestation Letters.

#### Note from Dan
This project was forked and refactored from the kairos-reporting-engine. All kudos should go to Tyler for Open Sourcing an awesome tool. I plan to actively use this for research at my day job. Where possible, I will attempt to integrate new features that Tyler releases for his project, and some of my own as I identify anything useful. If you have any ideas, open an "Issue" with a feature request and we can take a look at implementing it.

## Key Features

- **PDF Generation**: Export highly customized, professional PDF reports and formal Attestation Letters powered by Jinja2 and WeasyPrint.

- **Rich Text Editor**: Utilize a built-in rich text editor for writing comprehensive "Steps to Reproduce" and embedding proof-of-concept images.
- **Finding Imports**: This has been removed for now, but plan is to integrate importing findings in JSON format from tools like OSINT Industries.
- **Secure Authentication**: Built-in User Management, Passphrase Hashing (Argon2), and Multi-Factor Authentication (TOTP via Google Authenticator/Authy).
- **Risk Library**: Maintain a global library of common vulnerabilities with support for bulk CSV import/export.
- **Production Ready**: Ships with a utility to generate SSL certificates and runs securely on HTTPS port 443 with Streamlit telemetry and dev tools disabled.

## TODO:

- **Finding Imports**: Import findings via CSV (i.e: from tools like OSINT Industries)
- **Roles**: Implement RBAC for managers, supervisors, operatives (possibly clients)
- **Disclosure**: Attestation letters aren't really used in OSINT, but a Disclosure Report will make tasks court ready


## Prerequisites

For Docker deployment (including Windows), skip to the next section; host Python,
WeasyPrint libraries and OpenSSL are not required. For a native installation:
- Python 3.10 or higher
- System dependencies for WeasyPrint (e.g., `pango`, `cairo`, `libffi`).
  - On Ubuntu/Debian: `sudo apt-get install build-essential python3-dev python3-pip python3-setuptools python3-wheel python3-cffi libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info`
  - On macOS: `brew install pango cairo libffi`
- `openssl` for generating self-signed certificates.

## Docker

The recommended deployment on Windows, Linux, and macOS. The application runs in
a Linux container; Docker supplies Python, WeasyPrint, fonts, and OpenSSL.

### Windows prerequisites

- Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
  on a supported Windows version, following its WSL 2 requirements. Restart if requested.
- Start Docker Desktop and use its **WSL 2 backend** and **Linux containers**.
  This image does not use Windows containers.
- Install [Git for Windows](https://git-scm.com/downloads/win).
- Docker Desktop must be running whenever the application is needed. Check its
  licensing requirements for your organization.

On Linux or macOS, install Docker with the Docker Compose v2 plugin. The same
Compose commands apply. Windows Server requires a separately supported Linux
container host; these instructions target Docker Desktop on Windows.

### Start from PowerShell

Run these commands in PowerShell, not an administrator shell or Git Bash:

```powershell
docker version
docker compose version
git clone https://github.com/dandrews7396/osint-report-engine.git
cd osint-report-engine
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
```

The first build downloads dependencies and can take several minutes. Use a recent
Docker Desktop version if Compose does not recognize `--wait`.

Open **https://localhost:8443** on the Docker host, or
**https://<host-name-or-IP>:8443** from another machine. Create the initial
administrator account from the host before allowing other users to connect.
There are no default accounts or preloaded investigation records. Create manager
and investigator accounts to use the operational workflow.

First launch generates a local self-signed certificate for `localhost` and
`127.0.0.1`. A browser trust warning is expected for this certificate; only
proceed when you have verified that you are accessing your own instance.
Access using another host name or IP also produces a certificate-name mismatch
until you install a certificate covering that address. The built-in container
health check checks Streamlit's HTTPS endpoint.

The host port binds to **all host interfaces**, allowing network access.
Allow inbound TCP port **8443** through Windows Firewall for the intended network
profile and source addresses. Network routing and firewall rules determine which
machines can connect. Use appropriate access controls and a trusted certificate
for the host name used by clients; do not expose the service publicly without
reviewing the deployment's security.

### Persistent data

Three Compose-managed volumes preserve data across container replacement:

| Volume | Contents |
|---|---|
| `osint-data` | SQLite database (`kairos_osint.db`) and evidence uploads |
| `osint-reports` | Generated PDF reports |
| `osint-certs` | Local TLS certificate and private key |

Actual volume names have a Compose project prefix, for example
`osint-report-engine_osint-data`. Keep the same checkout directory/project name
when restarting or upgrading so Compose reuses the correct volumes.

Existing local databases, reports, credentials, and certificates are not copied
into the image. An existing database from an older application version may need
a schema migration; initialization does not migrate it automatically.

Templates are part of the image, not these volumes. Preserve any changes made in
the application's template editor before rebuilding or replacing a container.

### Everyday commands

```powershell
# Follow application logs (Ctrl+C exits logs, not the application).
docker compose logs -f osint

# Stop and remove the container, preserving its data volumes.
docker compose down

# Start again using the existing image and volumes.
docker compose up -d --wait --wait-timeout 180

# After backing up, pull source updates and rebuild.
git pull --ff-only
docker compose up -d --build --wait --wait-timeout 180
```

**Do not use `docker compose down -v` unless you intend to delete all application
data, reports, and certificates.** Volumes are persistence, not backups.

### Backup and restore (PowerShell)

Stop the application before copying SQLite and evidence so the backup is consistent:

```powershell
$backup = Join-Path $PWD ("backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
New-Item -ItemType Directory -Path $backup | Out-Null
docker compose stop osint
docker compose cp osint:/app/data "$backup/data"
docker compose cp osint:/app/reports "$backup/reports"
docker compose cp osint:/app/certs "$backup/certs"
docker compose start osint
```

Check that each copy succeeded before treating it as a backup. Store backups
securely outside the checkout; they contain investigation data and a private key.
Backups are excluded from Git and the image build.

To restore into a **new, empty deployment** of a compatible application version:

```powershell
$backup = "C:\Backups\osint\backup-20261019-120000"
docker compose create osint
docker compose cp "$backup/data/." osint:/app/data
docker compose cp "$backup/reports/." osint:/app/reports
docker compose cp "$backup/certs/." osint:/app/certs
docker compose up -d --wait --wait-timeout 180
```

Do not merge a backup over a running or populated deployment. Keep the original
backup until login, evidence, and report downloads have been verified.

### Using your own TLS certificate

For a fresh deployment, prepare a matching PEM certificate and private key.
The certificate must cover the DNS name or IP address clients use to connect:

```powershell
docker compose create osint
docker compose cp ./my-certs/cert.pem osint:/app/certs/cert.pem
docker compose cp ./my-certs/key.pem osint:/app/certs/key.pem
docker compose up -d --wait --wait-timeout 180
```

For an existing deployment, stop it before copying and start it afterward.
The entrypoint preserves an existing certificate/key pair.

### Troubleshooting

- **Cannot connect to Docker:** start Docker Desktop and wait for its engine.
- **Image/OS mismatch:** switch Docker Desktop to Linux containers.
- **Port 8443 already in use:** change the host port only, for example
  `9443:8443`, then use port `9443` in the browser and firewall rules.
- **Cannot connect from another machine:** use the Docker host's reachable name
  or IP, not `localhost`, and check Windows Firewall and network routing for
  inbound TCP port 8443.
- **Unhealthy container:** inspect `docker compose logs osint` and
  `docker inspect --format '{{json .State.Health}}' $(docker compose ps -q osint)`.
- **Shell-script errors after checkout:** shell files must use LF line endings;
  `.gitattributes` enforces this and the image normalizes its entrypoint.
- **Report rendering problems:** rebuild the image and check logs. Installing
  Windows GTK/Pango or a host Python environment is not necessary.

The Docker deployment workflow builds a clean image, checks HTTPS and PDF
generation, and verifies data survives container replacement.

---

## Quick Start (without Docker)

To quickly set up and launch the application from scratch, you can copy and paste this entire block into your terminal (assuming you have the prerequisites installed):

```bash
git clone https://github.com/dandrews7396/osint-report-engine.git
cd osint-report-engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
chmod +x generate_cert.sh
./generate_cert.sh
sudo .venv/bin/streamlit run app.py --server.port 443 --server.sslCertFile certs/cert.pem --server.sslKeyFile certs/key.pem --browser.gatherUsageStats false
```

## Installation

1. Clone the repository to your local machine.
2. Navigate to the project directory.
3. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Report layout

All eight selectable investigation types use a shared editorial layout with subject
profiles and finding cards grouped beneath each profile. Unlinked findings
(including those whose subject is no longer available) appear separately.
Compact risk counts replace the risk distribution graph, and the tools section
uses the same editorial styling with its heading and table kept together.
The shared layout is `templates/report_template.md`; each type-specific template
includes it and retains its own investigation title and data. Administrators can
edit **Shared editorial layout** on the Templates page to update all report types,
or replace a type-specific include with a custom layout for that type only.
No chart image is generated for templates without a chart slot.

### 1. Generate SSL Certificates
To run the application securely via HTTPS, first generate your self-signed certificates:
```bash
chmod +x generate_cert.sh
./generate_cert.sh
```

### 2. Start the Application
Because the application bounds to port 443 (a privileged port), start the server with `sudo`:
```bash
sudo .venv/bin/streamlit run --server.port 443 --server.headless true --server.sslCertFile certs/cert.pem --server.sslKeyFile certs/key.pem app.py
```

This will start the local Streamlit server. Navigate your web browser to `https://localhost` to access the application. On your first launch, you will be prompted to create the initial Administrator account.

## Directory Structure

- `app.py`: The lightweight Streamlit router and application entry point.
- `views/`: Modularized Python files containing the UI logic for every page in the application.
- `utils/`: Shared utilities, including authentication singletons and image processing helpers.
- `database/`: Contains SQLite database initialization (`db.py`) and CRUD operations (`operations.py`).
- `parsers/`: Contains parsing scripts for integrating external scanner outputs (e.g., Nessus, Burp Suite).
- `reporting/`: Contains the PDF generation engine (`generator.py`) utilizing WeasyPrint.
- `templates/`: Contains HTML/Markdown templates used for styling and formatting the generated PDF reports.
- `data/`: The default directory where the SQLite database (`kairos_osint.db`) and temporary files are stored.
- `reports/`: The default directory where generated PDF reports are saved.
- `certs/`: Directory containing your SSL certificates for HTTPS access.

## Database Note

The application uses a local SQLite database (`data/kairos_osint.db`). On the first run, the database and necessary tables will be created automatically.

## License

This project is released under a custom **Non-Commercial Share-Alike License**.

In summary:
- You are completely free to use, modify, and distribute the code.
- You **cannot** use this code for the purpose of re-selling or hosting it as a paid commercial service.
- It **must** remain completely open source, and any derivative works must also be released under these exact same terms.

See the [LICENSE](LICENSE) file for the full terms.
