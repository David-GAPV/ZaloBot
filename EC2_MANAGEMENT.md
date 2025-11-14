# EC2 Instance Management Guide

## Shutting Down the EC2 Instance

### Option 1: Stop Instance (Recommended - saves money)
```bash
# From your local machine
aws ec2 stop-instances --instance-ids i-0b6fb1c3c92c1a08d --profile david_gapv --region us-west-2
```

**Benefits:**
- Stops billing for compute (saves ~$49/month)
- EBS volume charges continue (~$1-2/month)
- Can restart anytime with same IP (if Elastic IP assigned)
- All data and configuration preserved

### Option 2: Terminate Instance (Permanent deletion)
```bash
# ⚠️ WARNING: This deletes the instance permanently
aws ec2 terminate-instances --instance-ids i-0b6fb1c3c92c1a08d --profile david_gapv --region us-west-2
```

## Starting the Instance Back Up

### 1. Start the EC2 Instance

**From AWS Console:**
1. Go to EC2 Dashboard → Instances
2. Select instance `i-0b6fb1c3c92c1a08d` (zalo-bot-t4g)
3. Click "Instance State" → "Start instance"
4. Wait ~1-2 minutes for instance to start

**From Command Line:**
```bash
aws ec2 start-instances --instance-ids i-0b6fb1c3c92c1a08d --profile david_gapv --region us-west-2
```

**Check instance status:**
```bash
aws ec2 describe-instances --instance-ids i-0b6fb1c3c92c1a08d --profile david_gapv --region us-west-2 --query 'Reservations[0].Instances[0].State.Name'
```

### 2. Get the New Public IP (if changed)

```bash
aws ec2 describe-instances --instance-ids i-0b6fb1c3c92c1a08d --profile david_gapv --region us-west-2 --query 'Reservations[0].Instances[0].PublicIpAddress'
```

**Note:** Public IP changes every time you stop/start unless you use an Elastic IP.

### 3. SSH into the Instance

```bash
ssh -i your-key.pem ubuntu@<NEW_PUBLIC_IP>
```

### 4. Start the Zalo Bot Service

#### Option A: Using Systemd (Automatic - Recommended)
The service will **start automatically** on boot if systemd is configured:

```bash
# Check service status
sudo systemctl status zalo-bot

# If not running, start it manually
sudo systemctl start zalo-bot

# View logs
sudo journalctl -u zalo-bot -f
# OR
tail -f /tmp/zalo_bot.log
```

#### Option B: Manual Start
If systemd is not configured or you prefer manual control:

```bash
cd /opt/zalo_bot
./startup.sh

# OR use restart script
./restart.sh
```

#### Option C: Direct Python Start
```bash
cd /opt/zalo_bot
nohup python3 app.py > /tmp/zalo_bot.log 2>&1 &
```

### 5. Verify Service is Running

```bash
# Check if service is listening on port 5000
lsof -i :5000

# Test health endpoint
curl http://localhost:5000/health

# Check logs
tail -f /tmp/zalo_bot.log
```

## Systemd Service Management

### Setup (One-time)
```bash
# The service is already configured and enabled
# To verify:
sudo systemctl is-enabled zalo-bot
```

### Service Commands
```bash
# Start service
sudo systemctl start zalo-bot

# Stop service
sudo systemctl stop zalo-bot

# Restart service
sudo systemctl restart zalo-bot

# Check status
sudo systemctl status zalo-bot

# View logs (real-time)
sudo journalctl -u zalo-bot -f

# View recent logs
sudo journalctl -u zalo-bot -n 50

# Disable auto-start (if needed)
sudo systemctl disable zalo-bot

# Re-enable auto-start
sudo systemctl enable zalo-bot
```

## Automatic Startup Configuration

✅ The Zalo Bot is configured to **automatically start** when the EC2 instance boots using systemd.

**What happens on EC2 start:**
1. Instance boots up
2. Network comes online
3. Systemd automatically starts `zalo-bot.service`
4. Service loads environment variables from `/opt/zalo_bot/.env`
5. Connects to AWS Bedrock (profile: david_gapv)
6. Connects to MongoDB
7. Flask server starts on port 5000
8. Service is ready to handle Zalo webhooks

**If startup fails:**
- Systemd will automatically retry every 10 seconds (configured in service file)
- Check logs: `sudo journalctl -u zalo-bot -n 100`
- Manual start: `sudo systemctl start zalo-bot`

## Troubleshooting

### Service Won't Start
```bash
# Check for errors
sudo systemctl status zalo-bot
sudo journalctl -u zalo-bot -n 50

# Check if port is already in use
lsof -i :5000

# Kill any conflicting process
pkill -f "python.*app.py"

# Try manual start
cd /opt/zalo_bot
python3 app.py
```

### AWS Connection Issues
```bash
# Verify credentials
aws sts get-caller-identity --profile david_gapv

# Test Bedrock access
python3 -c "import boto3; boto3.Session(profile_name='david_gapv', region_name='us-west-2').client('bedrock-runtime'); print('✓ AWS OK')"
```

### MongoDB Connection Issues
```bash
# Test MongoDB connection
python3 -c "from uit_knowledge_base_mongodb import UITMongoKnowledgeBase; import os; from dotenv import load_dotenv; load_dotenv(); kb=UITMongoKnowledgeBase(os.getenv('MONGODB_URI')); print(f'✓ MongoDB OK - {kb.count_documents()} docs')"
```

## Cost Optimization

### When to Stop the Instance
- **Stop during non-business hours** to save money
- **Stop for weekends** if not needed 24/7
- Example: Run only 8am-6pm = ~60% cost savings

### Cost Comparison
- **Running 24/7:** $49.06/month
- **Running 12 hours/day:** ~$24.53/month
- **Running 8 hours/day:** ~$16.35/month
- **Stopped:** ~$1-2/month (EBS storage only)

### Scheduling Stop/Start
Create cron jobs or use AWS Instance Scheduler:

**Stop at 6 PM:**
```bash
0 18 * * * aws ec2 stop-instances --instance-ids i-0b6fb1c3c92c1a08d --profile david_gapv --region us-west-2
```

**Start at 8 AM:**
```bash
0 8 * * * aws ec2 start-instances --instance-ids i-0b6fb1c3c92c1a08d --profile david_gapv --region us-west-2
```

## Important Notes

1. **Elastic IP:** Consider attaching an Elastic IP to keep the same public IP address after restarts
2. **Zalo Webhook:** Update Zalo webhook URL if public IP changes
3. **MongoDB:** Ensure MongoDB instance is also running before starting Zalo bot
4. **Auto-start:** Systemd service is enabled, so bot starts automatically on instance boot
5. **Logs:** Logs are at `/tmp/zalo_bot.log` (cleared on reboot) and systemd journal

## Quick Reference

```bash
# EC2 Management
aws ec2 stop-instances --instance-ids i-0b6fb1c3c92c1a08d --profile david_gapv --region us-west-2
aws ec2 start-instances --instance-ids i-0b6fb1c3c92c1a08d --profile david_gapv --region us-west-2

# Service Management (after SSH)
sudo systemctl status zalo-bot    # Check status
sudo systemctl start zalo-bot     # Start service
sudo systemctl stop zalo-bot      # Stop service
sudo systemctl restart zalo-bot   # Restart service

# Manual Management (alternative)
cd /opt/zalo_bot
./restart.sh                      # Restart manually
./check_config.sh                 # Check configuration
python3 test_system.py            # Run tests

# Monitoring
tail -f /tmp/zalo_bot.log         # Watch logs
curl http://localhost:5000/health # Check health
```

---

**Instance ID:** i-0b6fb1c3c92c1a08d  
**Instance Name:** zalo-bot-t4g  
**Region:** us-west-2  
**Auto-start:** ✅ Enabled via systemd
