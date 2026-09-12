# ShotCraft EC2 deployment

This runbook deploys the frontend and FastAPI backend together on one Amazon
Linux 2023 EC2 instance. SQLite remains on the instance's attached EBS volume,
so do not terminate the instance or delete that volume without first taking a
snapshot of `data/shotcraft.db`.

## 1. Create the instance

- **AMI:** Amazon Linux 2023
- **Instance type:** `t3.small`
- **Storage:** 30 GB `gp3` EBS
- **Security group:** allow HTTP (TCP 80) from the internet and SSH (TCP 22)
  only from your own current IP address. Do not expose port 8000.

Attach an EC2 instance role with `bedrock-agentcore:InvokeAgentRuntime` scoped
to the ShotCraft runtime and its `runtime-endpoint/*` resources. Do not install
personal AWS access keys on the instance.

Associate an Elastic IP if you need a stable public address. For a short
hackathon demo, using the EC2 public DNS name is also fine.

## 2. Install the app

SSH to the instance and run:

```bash
sudo dnf update -y
sudo dnf install -y git nginx python3.11 python3.11-pip

sudo useradd --system --create-home --shell /sbin/nologin shotcraft
sudo mkdir -p /opt/shotcraft
sudo chown shotcraft:shotcraft /opt/shotcraft
sudo -u shotcraft git clone <YOUR_REPOSITORY_URL> /opt/shotcraft/app
sudo -u shotcraft python3.11 -m venv /opt/shotcraft/venv
sudo -u shotcraft /opt/shotcraft/venv/bin/pip install --upgrade pip
sudo -u shotcraft /opt/shotcraft/venv/bin/pip install -r /opt/shotcraft/app/requirements.txt
sudo -u shotcraft mkdir -p /opt/shotcraft/app/data /opt/shotcraft/app/static/generated
```

Use the same deployment branch or commit that you tested locally.

## 3. Configure secrets

Create the environment file. It is deliberately outside the Git checkout:

```bash
sudo mkdir -p /etc/shotcraft
sudo nano /etc/shotcraft/shotcraft.env
sudo chmod 600 /etc/shotcraft/shotcraft.env
```

Example contents (use real values, never commit this file):

```dotenv
AWS_REGION=us-west-2
SHOTCRAFT_AGENTCORE_ENABLED=true
SHOTCRAFT_AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-west-2:ACCOUNT_ID:runtime/RUNTIME_ID
OPENAI_API_KEY=replace_with_your_openai_key
SHOTCRAFT_IMAGE_MODEL=gpt-image-2.5-flare
```

The deployed AgentCore runtime reads its Mantle key from Secrets Manager. The
EC2 app does not need that bearer key unless you intentionally enable local
Strands fallback. Keep the production EC2 role limited to invoking AgentCore.

If you are demoing without external image generation, omit `OPENAI_API_KEY` and
do not use the moodboard-image generation action.

## 4. Start the service

```bash
sudo cp /opt/shotcraft/app/deploy/shotcraft.service /etc/systemd/system/shotcraft.service
sudo cp /opt/shotcraft/app/deploy/nginx-shotcraft.conf /etc/nginx/conf.d/shotcraft.conf
sudo rm -f /etc/nginx/conf.d/default.conf
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable --now shotcraft nginx
curl http://127.0.0.1/healthz
```

The last command should return `{"status":"ok"}`. Then visit
`http://<EC2-PUBLIC-DNS>/` in a browser.

## Updating the app

```bash
sudo -u shotcraft git -C /opt/shotcraft/app pull
sudo -u shotcraft /opt/shotcraft/venv/bin/pip install -r /opt/shotcraft/app/requirements.txt
sudo systemctl restart shotcraft
sudo systemctl status shotcraft --no-pager
```

Logs are available through `sudo journalctl -u shotcraft -f`.

## Data and image persistence

- SQLite data: `/opt/shotcraft/app/data/shotcraft.db`
- Temporary generated images: `/opt/shotcraft/app/static/generated/`

For the hackathon, take an EBS snapshot before major changes. Before a more
durable deployment, move generated images to a private S3 bucket and save each
object key in SQLite. Do not store generated images in Git.
