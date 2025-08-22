# 🚀 Google Drive Transfer Tool

A high-performance tool to transfer files and folders between Google Drive accounts while preserving the complete folder structure. Optimized for maximum speed using parallel processing and intelligent rate limiting.

## ✨ Features

- **🔄 Complete Transfer**: Transfer all files and folders between Google Drive accounts
- **📁 Structure Preservation**: Maintains exact folder hierarchy and organization
- **⚡ Maximum Speed**: Uses parallel processing with configurable worker threads
- **🛡️ Rate Limit Handling**: Smart retry logic with exponential backoff
- **📊 Real-time Progress**: Live progress tracking with file and byte counts
- **📄 Google Docs Support**: Converts Google Docs to Microsoft Office formats
- **🔄 Resume Capability**: Handles interruptions gracefully with retry mechanisms
- **🎛️ Configurable**: Adjustable settings for workers, chunk sizes, and retry policies

## 🛠️ Prerequisites

- Python 3.7 or higher
- Google Cloud Console project with Drive API enabled
- OAuth 2.0 credentials (JSON file)
- Two Google Drive accounts (source and destination)

## 📋 Setup Instructions

### 1. Google Cloud Console Setup

**You can use ANY Google account for this step** - it doesn't have to be your source or destination account.

#### 🔍 Navigation Guide:

```
Google Cloud Console
├── 1. Select/Create Project
├── 2. APIs & Services
│   ├── Library
│   │   └── Search: "Google Drive API" → Enable
│   └── Credentials
│       ├── + CREATE CREDENTIALS (top button)
│       ├── OAuth 2.0 client IDs
│       └── Create OAuth client ID
│           ├── Application type: Desktop app
│           ├── Name: "Google Drive Transfer Tool"
│           └── CREATE → Download JSON
```

#### 📋 Step-by-Step Instructions:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Drive API:
   - Click "APIs & Services" in the left sidebar
   - Click "Library" in the left menu
   - Search for "Google Drive API" and click on it
   - Click "ENABLE" button
4. Create OAuth 2.0 credentials:
   - Click "APIs & Services" > "Credentials" in the left sidebar
   - Click the **"+ CREATE CREDENTIALS"** button (at the top of the page)
   - Select **"OAuth 2.0 client IDs"** from the dropdown menu
   - On the "Create OAuth client ID" page:
     - **Application type**: Choose **"Desktop app"**
     - **Name**: Enter "Google Drive Transfer Tool"
   - Click **"CREATE"**
   - Download the JSON file and rename it to `credentials.json`

**Note:** This `credentials.json` file is just for the application to authenticate. You'll choose your actual source and destination Google Drive accounts when you run the transfer.

### 1.5 Verify Your Credentials (Optional)

After downloading `credentials.json`, you can verify it's correct:

```bash
python3 verify_credentials.py
```

This will check if your credentials file is properly formatted and ready to use.

### 2. Installation

```bash
# Clone or download the project
cd /path/to/GoogleDriveTransfer

# Install dependencies
pip install -r requirements.txt

# Make script executable (optional)
chmod +x drive_transfer.py

### 2.1 Authentication Flow

**See exactly what happens:** `python3 auth_demo.py`

**Diagnose network issues:** `python3 network_diagnostic.py`

When you run the transfer tool, you'll see this authentication process:

```
🔐 Authenticating with Google Drive...
📁 Setting up source account...
[Browser opens with Google OAuth URL]
[Sign in with SOURCE Google account]
📁 Setting up destination account...
[Browser opens again with Google OAuth URL]
[Sign in with DESTINATION Google account]
✅ Authentication successful!
```

**Important:** You need to authenticate **TWO separate Google accounts**:
- **Source account**: Where files are coming FROM
- **Destination account**: Where files are going TO

The browser will open **twice** - once for each account.
```

### 3. Configuration

1. Place your `credentials.json` file in the project directory
2. Get your folder IDs:
   - Open Google Drive in your browser
   - Navigate to the source folder
   - Copy the folder ID from the URL (after `/folders/`)
   - Do the same for the destination folder

## 🚀 Usage

### Command Line Interface

```bash
# Basic transfer with 8 parallel workers
python drive_transfer.py --source SOURCE_FOLDER_ID --dest DEST_FOLDER_ID

# Custom number of workers for maximum performance
python drive_transfer.py --source SOURCE_FOLDER_ID --dest DEST_FOLDER_ID --workers 16

# Save configuration for repeated use
python drive_transfer.py --source SOURCE_FOLDER_ID --dest DEST_FOLDER_ID --config
```

### Configuration File

Edit `transfer_config.json`:

```json
{
  "source_folder_id": "your_source_folder_id",
  "dest_folder_id": "your_dest_folder_id",
  "max_workers": 8,
  "chunk_size": 8388608,
  "max_retries": 3,
  "retry_delay": 1.0,
  "rate_limit_delay": 0.1,
  "progress_interval": 10
}
```

### Authentication Flow

1. **First Run**: The script will open your browser for authentication
2. **Source Account**: Authenticate with the source Google Drive account
3. **Destination Account**: Authenticate with the destination Google Drive account
4. **Token Storage**: Credentials are saved as `source_token.pickle` and `destination_token.pickle`

## ⚙️ Configuration Options

| Parameter | Description | Default | Recommended |
|-----------|-------------|---------|-------------|
| `max_workers` | Number of parallel transfer threads | 8 | 8-16 (based on your CPU cores) |
| `chunk_size` | File chunk size for uploads (bytes) | 8MB | 8MB-16MB |
| `max_retries` | Maximum retry attempts | 3 | 3-5 |
| `retry_delay` | Base delay between retries (seconds) | 1.0 | 1.0-2.0 |
| `rate_limit_delay` | Delay to avoid rate limiting (seconds) | 0.1 | 0.1-0.5 |
| `progress_interval` | Progress update frequency | 10 | 5-20 |
| `network_timeout` | Network operation timeout (seconds) | 300 | 300-600 for slow connections |
| `enable_resumable` | Enable resumable uploads | true | Keep enabled for reliability |

## 📊 Performance Optimization

### CPU Usage Maximization

The tool uses ThreadPoolExecutor to maximize CPU utilization:

```python
# Example: 16 workers for high-end systems
python drive_transfer.py --source ID --dest ID --workers 16
```

### Rate Limiting Strategy

- **Exponential Backoff**: Automatically increases wait time on rate limit errors
- **Smart Delays**: Minimal delays between operations to stay within quotas
- **Error Handling**: Graceful handling of API errors and temporary failures

### Memory Management

- **Streaming**: Files are streamed in chunks to minimize memory usage
- **Progress Tracking**: Efficient progress updates without memory overhead
- **Parallel Processing**: Controlled thread pool prevents memory exhaustion

## 🔍 Supported File Types

### Regular Files
- All standard file formats (PDF, DOC, XLS, PPT, images, videos, etc.)
- Large files supported with resumable uploads

### Google Workspace Files
- **Google Docs** → Microsoft Word (.docx)
- **Google Sheets** → Microsoft Excel (.xlsx)
- **Google Slides** → Microsoft PowerPoint (.pptx)
- **Other Google files** → Skipped with warning

## 📈 Monitoring and Progress

The tool provides real-time progress tracking:

```
🔐 Authenticating with Google Drive...
📁 Setting up source account...
📁 Setting up destination account...
✅ Authentication successful!
📋 Scanning source folder structure...
🏗️ Creating folder structure...
📁 Created folder: Documents/Work
🚀 Starting transfer of 1,234 files (45.67 GB)
📊 Progress: 50/1234 files (4.1%)
⬇️ Downloading large_file.zip: 67%
⬆️ Uploading large_file.zip: 89%
✅ Transferred: large_file.zip
📊 Progress: 100/1234 files (8.1%)
🎉 Transfer completed!
```

## 🔐 Authentication Troubleshooting

### Common Authentication Issues:

**❌ "Browser doesn't open"**
- **Solution**: Copy the URL manually and paste it in your browser

**❌ "Invalid credentials"**
- **Solution**: Download fresh `credentials.json` from Google Cloud Console

**❌ "Access denied" or "Permission denied"**
- **Solution**: Make sure you're signed in with the correct Google account
- **Check**: Ensure the account has Google Drive enabled

**❌ "Token expired" or "Re-authentication needed"**
- **Solution**: Delete `source_token.pickle` and `destination_token.pickle` files

**❌ "This app isn't verified" warning**
- **Solution**: Click "Advanced" → "Go to Google Drive Transfer Tool (unsafe)"
- This is normal for personal apps

### Token Management:
- **Token files**: `source_token.pickle`, `destination_token.pickle`
- **Location**: Saved in the project directory
- **Re-auth**: Delete these files to force re-authentication

## 🌐 Network Troubleshooting

### Common Network Issues:

**❌ "IncompleteRead" errors**
- **Cause**: Network connection interrupted during download
- **Solutions**:
  - Use a more stable internet connection
  - Reduce workers: `--workers 4`
  - Increase timeout: `--timeout 600`
  - Use smaller chunks: `--chunk-size 4194304`

**❌ "SSL: DECRYPTION_FAILED" or "bad record mac"**
- **Cause**: SSL/TLS connection issues, often with unstable connections
- **Solutions**:
  - Switch to a wired connection if possible
  - Reduce parallel workers: `--workers 2`
  - Increase timeout: `--timeout 600`
  - Disable resumable uploads: `--disable-resumable`

**❌ "Connection reset" or "Connection aborted"**
- **Cause**: Network interruptions or firewall issues
- **Solutions**:
  - Check firewall settings
  - Use VPN if behind corporate firewall
  - Reduce workers: `--workers 1`
  - Increase retry delay: Edit `transfer_config.json`

### Network Optimization Commands:

```bash
# For unstable connections:
python3 drive_transfer.py --source ID --dest ID --workers 2 --timeout 600

# For very slow connections:
python3 drive_transfer.py --source ID --dest ID --workers 1 --timeout 900 --chunk-size 4194304

# For maximum reliability (slower):
python3 drive_transfer.py --source ID --dest ID --workers 1 --disable-resumable
```

## 🛡️ Error Handling

### Common Issues and Solutions

1. **Rate Limiting**:
   ```
   ⚠️ Rate limit hit, waiting 2.0s...
   ```
   - Automatically handled with exponential backoff
   - Adjust `rate_limit_delay` if needed

2. **Authentication Errors**:
   ```
   ❌ credentials.json not found
   ```
   - Ensure `credentials.json` is in the project directory
   - Re-download from Google Cloud Console if corrupted

3. **Permission Errors**:
   ```
   ❌ Error creating folder: Insufficient permissions
   ```
   - Check folder sharing permissions
   - Ensure destination account has write access

4. **Network Issues**:
   ```
   ❌ Connection timeout
   ```
   - Check internet connection
   - Script will automatically retry with backoff

## 🚨 Safety Features

- **Dry Run Mode**: Preview transfers without making changes (planned)
- **Resume Capability**: Continue interrupted transfers
- **Checksum Verification**: Ensure file integrity (planned)
- **Error Recovery**: Graceful handling of partial failures

## 🔧 Troubleshooting

### Debug Mode

Add debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Issues

1. **"Insufficient permissions"**
   - Check folder sharing settings
   - Ensure OAuth scopes are correct

2. **"File not found"**
   - Verify folder IDs are correct
   - Check if files were deleted during transfer

3. **"Rate limit exceeded"**
   - Reduce number of workers
   - Increase rate_limit_delay

4. **"Memory error"**
   - Reduce max_workers
   - Increase system RAM

## 📝 Example Use Cases

### Large Data Migration
```bash
# Transfer company documents with high parallelism
python drive_transfer.py --source 1ABC... --dest 2DEF... --workers 12
```

### Personal Backup
```bash
# Transfer personal files with moderate speed
python drive_transfer.py --source 1ABC... --dest 2DEF... --workers 4
```

### Automated Sync
```bash
# Add to cron for automated transfers
0 2 * * * cd /path/to/GoogleDriveTransfer && python drive_transfer.py --source ID --dest ID
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

- Use at your own risk
- Ensure you have proper permissions for file transfers
- Monitor your Google Drive API quotas
- Backup important data before transfer

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review Google Drive API documentation
3. Create an issue in the repository

---

**Happy Transferring! 🚀**
