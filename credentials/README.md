# Credentials Directory

Place your `google_sheets_credentials.json` file here.

This file contains your Google service account credentials for accessing Google Sheets.

## How to get this file:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google Sheets API and Google Drive API
4. Create a service account (IAM & Admin > Service Accounts)
5. Create a JSON key for the service account
6. Save it here as `google_sheets_credentials.json`

**Important:** Add this file to `.gitignore` to avoid committing credentials!

