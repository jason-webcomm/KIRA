# Gitea Integration

Integrating Gitea API allows KIRA to manage code repositories.

## 📋 Prerequisites

- Gitea account (gitea.com or Self-hosted)
- Personal Access Token
- Gitea MCP Server running in HTTP mode

---

## 🔑 Step 1: Generate Access Token

### 1. Access Gitea
- [Gitea.com](https://gitea.com) or your company's Gitea server

### 2. Create Personal Access Token
1. Click profile icon in top right
2. Select **"Settings"**
3. Click **"Applications"** in left menu
4. Scroll to **"Access Tokens"** section
5. Click **"Generate New Token"**

### 3. Configure Token
- **Token Name**: `KIRA Bot` (any name you want)
- **Expiration**: Set expiration (optional)
- **Select scopes**: Choose these permissions
  - ✅ `read:repository` - Read repositories
  - ✅ `write:repository` - Write repositories
  - ✅ `read:user` - Read user info
  - ✅ `read:issue` - Read issues
  - ✅ `write:issue` - Write issues

### 4. Generate and Copy Token
1. Click **"Generate Token"**
2. Copy generated token (shown only once!)
3. Store securely

::: warning Token Security
Personal Access Token is shown only once.
Store it safely as you cannot view it again.
:::

---

## 🌐 Step 2: Start Gitea MCP Server (HTTP Mode)

Gitea MCP server needs to be running in HTTP mode for KIRA to connect.

### Option A: Run Locally

1. Install Gitea MCP server:
```bash
npm install -g gitea-mcp
```

2. Start the server in HTTP mode:
```bash
gitea-mcp --transport streamable-http --port 8080
```

The server will be available at `http://localhost:8080/mcp`

### Option B: Run with Docker

```bash
docker run -d \
  -p 8080:8080 \
  -e GITEA_ACCESS_TOKEN=<your_token> \
  gitea/gitea-mcp:latest \
  --transport streamable-http --port 8080
```

---

## ⚙️ Step 3: Configure KIRA

### 1. Launch KIRA App
Open the Environment Variables tab.

### 2. Find Gitea Section
**MCP Settings** > **Gitea**

### 3. Enable Setting
- Turn the toggle switch **ON**

### 4. Enter Information
- **GITEA_HOST**: Gitea server URL
  - Gitea.com: `https://gitea.com`
  - Self-hosted: `https://git.company.com`
- **GITEA_ACCESS_TOKEN**: The Access Token you copied
- **GITEA_MCP_HTTP_URL**: MCP server HTTP URL
  - Local: `http://localhost:8080/mcp`
  - Remote: `http://your-server:8080/mcp`

### 5. Save Settings
- Click **"Save Settings"** button
- Restart server

---

## ✅ Step 4: Test

Ask KIRA on Slack:

```
Show me my Gitea repositories
```

```
Tell me recent commits for repo "myapp"
```

KIRA will fetch information via Gitea API.

---

## 🎯 Usage Examples

### Repository Query
```
User: Show me Gitea repository list
KIRA: [Gitea query]
      1. user/project-alpha
      2. user/project-beta
      3. my-app
```

### Issue Management
```
User: Create an issue in "my-app" repo: "Bug fix needed"
KIRA: [Gitea issue created] Created issue #42.
```

### Commit Query
```
User: Show me last 5 commits in "my-app"
KIRA: [Gitea query]
      1. fix: Login bug fix
      2. feat: Add new feature
      ...
```

### Pull Request Query
```
User: Show me my PRs
KIRA: [Gitea query]
      1. PR #123: Feature improvement
      2. PR #124: Bug fix
```

---

## 🔧 Troubleshooting

### "MCP server failed to start"
- Verify Gitea MCP server is running
- Check `GITEA_MCP_HTTP_URL` is correct
- Ensure the server is accessible from KIRA

### "Authentication failed"
- Verify Access Token is correct
- Check if token has expired
- Verify token is active on Gitea

### "Connection refused"
- Check if Gitea MCP server is running on the specified port
- Verify firewall settings
- Ensure the URL protocol (http/https) is correct

### "Permission denied"
- Check Access Token permissions (scopes)
- Need `read:repository`, `write:repository` permissions
- Verify repository access permissions

### Cannot access specific repository
- Confirm you're a member of that repository
- Check permissions if repository is Private

---

## 💡 Tips

### Self-hosted Gitea
When using internal company Gitea server:
- Enter company Gitea address in GITEA_HOST
- Example: `https://git.company.com`

### MCP Server Deployment
For production deployment:
- Run MCP server on a dedicated machine
- Use HTTPS with proper SSL certificates
- Configure reverse proxy (nginx) if needed
- Set up process manager (systemd, PM2) to keep server running

### Token Management
- Set clear token name (`KIRA Bot`)
- Set expiration for security
- Rotate tokens regularly

### Minimize Permissions
Grant only necessary permissions:
- Read-only: Select only `read:repository`
- Need write: Add `write:repository`
- Full access: Add `read:user`, `read:issue`, `write:issue`

### Effective Usage
- Specify repository names clearly in `owner/repo` format
- Enter branch names exactly
- Quick lookup via issue/PR numbers

---

## 🔗 Related Links

- [Gitea Documentation](https://docs.gitea.com/)
- [Gitea MCP Server](https://gitea.com/gitea/gitea-mcp)
- [Personal Access Tokens](https://docs.gitea.com/next/usage/advanced/applications)