# Deployment Guide for KOKO Roadmap

This guide covers multiple ways to deploy the KOKO Roadmap application so your colleagues can access it.

## Option 1: Render.com (Recommended - Free & Easy)

### Steps:

1. **Create a GitHub repository** (if you haven't already):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Sign up at Render.com**:
   - Go to https://render.com
   - Sign up with GitHub

3. **Create a new Web Service**:
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the repository
   - Use these settings:
     - **Name**: koko-roadmap
     - **Environment**: Python 3
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn app:app`
     - **Instance Type**: Free (or upgrade for better performance)

4. **Set Environment Variables** (optional):
   - `KOKO_ROADMAP_XLSX`: roadmap.xlsx (default)
   - `KOKO_ROADMAP_CHANGELOG`: changelog.csv (default)

5. **Deploy**:
   - Click "Create Web Service"
   - Wait for deployment (5-10 minutes)
   - Your app will be available at: `https://koko-roadmap.onrender.com`

**Note**: Free tier on Render spins down after 15 minutes of inactivity. First request may take 30-60 seconds.

---

## Option 2: Railway.app (Fast & Reliable)

1. **Sign up at Railway.app**: https://railway.app
2. **Create new project** → "Deploy from GitHub repo"
3. **Select your repository**
4. Railway auto-detects Python and deploys
5. Your app will be live at: `https://your-app.railway.app`

**Note**: Railway offers $5/month credit, enough for small apps.

---

## Option 3: Fly.io (Good Performance)

1. **Install Fly CLI**: https://fly.io/docs/getting-started/installing-flyctl/
2. **Sign up**: `fly auth signup`
3. **Deploy**:
   ```bash
   fly launch
   ```
4. Follow prompts (use defaults)
5. Your app: `https://your-app.fly.dev`

---

## Option 4: Local Network Sharing (Same Office)

If your colleagues are on the same network:

1. **Find your IP address**:
   - Windows: `ipconfig` (look for IPv4 Address)
   - Mac/Linux: `ifconfig` or `ip addr`

2. **Update app.py** to allow external connections:
   ```python
   if __name__ == '__main__':
       app.run(host='0.0.0.0', port=5000, debug=False)
   ```

3. **Run the app**:
   ```bash
   python app.py
   ```

4. **Share the URL**: `http://YOUR_IP:5000`
   - Example: `http://192.168.1.100:5000`

**Security Note**: This exposes the app to your local network only. For internet access, use Options 1-3.

---

## Option 5: Self-Hosted Server (VPS)

If you have a VPS (DigitalOcean, AWS EC2, etc.):

1. **SSH into your server**
2. **Install Python and dependencies**:
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip
   pip3 install -r requirements.txt
   ```

3. **Use a process manager** (PM2 or systemd):
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

4. **Set up Nginx** as reverse proxy (optional but recommended)

---

## Important Notes

### Excel File Storage
- **Render/Railway/Fly**: Files are stored in the filesystem but may be lost on redeploy
- **Solution**: Use a database (SQLite/PostgreSQL) or cloud storage (S3) for production
- For now, the Excel file persists between deployments on Render

### Multi-User Considerations
- The current Excel-based storage may have concurrency issues with multiple simultaneous users
- Consider migrating to a database (SQLite for small teams, PostgreSQL for larger)

### Security
- Add authentication if deploying publicly
- Consider using Flask-Login or similar
- Don't expose sensitive data without proper security

---

## Quick Start (Render.com)

**Fastest way to get live:**

1. Push code to GitHub
2. Go to render.com → New Web Service
3. Connect repo → Deploy
4. Share URL with colleagues

**That's it!** 🚀

---

## Troubleshooting

### "Module not found" errors
- Ensure `requirements.txt` includes all dependencies
- Check build logs in Render dashboard

### Excel file not found
- Ensure `roadmap.xlsx` exists in the repo (or is created on first run)
- Check file permissions

### App crashes on startup
- Check logs in deployment dashboard
- Ensure Python version matches (3.12 recommended)

### Can't access from other computers (local)
- Check firewall settings
- Ensure using `host='0.0.0.0'` in app.run()
- Verify IP address is correct

