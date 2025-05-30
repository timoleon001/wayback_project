# Wayback Script

This script retrieves archived webpage titles from the Wayback Machine and writes them to a Google Sheets spreadsheet. It processes domains listed in the first column of the spreadsheet, queries the Wayback Machine for the latest snapshots (up to 3 by default), extracts the `<title>` content from the oldest snapshot, and writes it to the last available column. The process is logged, with data saved to the `wayback_script.log` file.

## Features
- Retrieves up to 3 snapshots per domain from the Wayback Machine.
- Extracts the `<title>` from the oldest snapshot.
- Writes results to a Google Sheets spreadsheet in batches (default batch size: 5 domains).
- Includes detailed logging for debugging and monitoring.
- Handles errors gracefully (e.g., timeouts, missing titles, API quota limits).

## Prerequisites
- **Python 3.6+**: Ensure Python 3 is installed on your system.
- **Google Sheets API Credentials**:
  - You need a `credentials.json` file to authenticate with the Google Sheets API.
  - **How to obtain `credentials.json`**:  
    1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
    2. Create a new project (or select an existing one).
    3. Enable the Google Sheets API and Google Drive API:  
       - Navigate to "APIs & Services" > "Library".  
       - Search for "Google Sheets API" and "Google Drive API", and enable both.
    4. Create a service account:  
       - Go to "IAM & Admin" > "Service Accounts".  
       - Click "Create Service Account", fill in the details, and create.  
       - Grant the service account "Editor" role (or assign specific roles for Sheets and Drive).  
       - After creation, click on the service account, go to the "Keys" tab, and click "Add Key" > "Create new key".  
       - Select "JSON" format and download the key file—this is your `credentials.json`.  
    5. Place the `credentials.json` file in the project directory.
    6. Share your Google Sheet with the service account email (e.g., `sheets-editor@your-project-id.iam.gserviceaccount.com`) with Editor permissions.
- **Internet Access**: Required for querying the Wayback Machine and Google Sheets API.

## Installation
1. **Clone or Download the Script**:
   - Save the script as `wayback_script.py` in a project directory (e.g., `~/wayback_project`).

2. **Install Dependencies**:
   - Install required Python libraries:
     ```bash
     pip install gspread google-auth requests beautifulsoup4
     ```
   - Optionally, use a virtual environment:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     pip install gspread google-auth requests beautifulsoup4
     ```

3. **Set Up Google Sheets**:
   - Ensure your spreadsheet URL is correctly set in the script (`SPREADSHEET_URL`).
   - The spreadsheet should have at least one sheet with domains listed in the first column (starting from row 2, row 1 is assumed to be a header).

4. **Add `credentials.json`**:
   - Place the `credentials.json` file in the same directory as the script.

## Usage
1. **Run the Script**:
   - Navigate to the project directory:
     ```bash
     cd ~/wayback_project
     ```
   - If using a virtual environment, activate it:
     ```bash
     source venv/bin/activate
     ```
   - Run the script:
     ```bash
     python3 wayback_script.py
     ```

2. **Check Results**:
   - Results are written to the Google Sheet in the first empty column for each domain.
   - If a title is found, it’s written as-is. If not, an error message is recorded (e.g., "нет доступных снимков", "Ошибка: не удалось извлечь <title>", or "N/A").

3. **View Logs**:
   - Logs are saved to `wayback_script.log` in the project directory.
   - Check this file for detailed information on the script’s execution, including errors and warnings.

## Running on a Server
1. **Connect to the Server**:
   - Use SSH to connect:
     ```bash
     ssh username@server_ip
     ```

2. **Set Up the Environment**:
   - Install Python and dependencies (see Installation section above).
   - Upload the script and `credentials.json` to the server:
     ```bash
     scp wayback_script.py credentials.json username@server_ip:~/wayback_project/
     ```

3. **Run the Script**:
   - Follow the same steps as in the Usage section.
   - To run in the background:
     ```bash
     nohup python3 wayback_script.py &
     ```

4. **Automate with Cron** (optional):
   - Schedule the script to run daily at 8 AM:
     ```bash
     crontab -e
     ```
     Add the following line:
     ```bash
     0 8 * * * /bin/bash -c 'cd ~/wayback_project && source venv/bin/activate && python3 wayback_script.py >> ~/wayback_project/cron.log 2>&1'
     ```

## Troubleshooting
- **"Permission Denied" for Google Sheets**:
  - Ensure the service account email has Editor access to the spreadsheet.
- **"HTTPSConnectionPool... Read timed out"**:
  - Increase `REQUEST_TIMEOUT` or `WAYBACK_REQUEST_DELAY` in the script.
  - Check your internet connection.
- **"Quota Exceeded" (Google Sheets API Error 429)**:
  - The script automatically waits 60 seconds and retries.
  - Increase `SHEETS_REQUEST_DELAY` or reduce `BATCH_SIZE` to lower the request rate.
- **Log File Encoding Issues**:
  - The script uses UTF-8 encoding. Ensure your text editor uses UTF-8 when viewing `wayback_script.log`.

## Limitations
- **Google Sheets API Quotas**:
  - Free tier limits: ~60 requests per minute per user.
  - With `BATCH_SIZE = 5`, you can process ~200–250 domains per minute safely.
- **Wayback Machine Access**:
  - The script may encounter timeouts if the Wayback Machine is slow or rate-limits your IP.
  - Adjust `MAX_RETRIES` and `WAYBACK_REQUEST_DELAY` as needed.

## License
This script is provided as-is for personal use. Modify and distribute as needed.