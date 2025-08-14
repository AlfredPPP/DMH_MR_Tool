# docs/user-guide/README.md

# DMH MR Tool - User Guide

## Welcome

Welcome to the DMH MR Tool User Guide. This tool automates the collection and processing of Australian financial market data, reducing daily processing time from 2-3 hours to under 30 minutes.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Installation](#installation)
3. [User Interface Overview](#user-interface-overview)
4. [Spider Module](#spider-module)
5. [Parser Module](#parser-module)
6. [MR Update Module](#mr-update-module)
7. [Database Browser](#database-browser)
8. [Settings](#settings)
9. [Common Workflows](#common-workflows)
10. [Troubleshooting](#troubleshooting)
11. [Keyboard Shortcuts](#keyboard-shortcuts)
12. [Best Practices](#best-practices)

## Getting Started

### Prerequisites
- Windows 10 or later
- Access to shared network drives
- DMH system credentials
- Automation Launcher installed

### First-Time Setup
1. Download the `.gmas` file from the internal portal
2. Double-click to install via Automation Launcher
3. On first launch, verify network drive access
4. Configure your user settings

## Installation

### Step-by-Step Installation

1. **Download the Application**
   - Navigate to the GMAS portal: `http://gmas.internal`
   - Search for "DMH MR Tool"
   - Click "Download" to get the `.gmas` file (~8KB)

2. **Install via Automation Launcher**
   - Locate the downloaded `.gmas` file
   - Double-click to open with Automation Launcher
   - Click "Install" when prompted
   - Wait for installation to complete (~30 seconds)

3. **Initial Configuration**
   - Launch DMH MR Tool from Start Menu or Desktop
   - Enter your username when prompted
   - Verify database connection (green indicator)

## User Interface Overview

### Main Window Layout

```
┌─────────────────────────────────────────────────┐
│  DMH MR Tool                          [─][□][×] │
├─────────────┬───────────────────────────────────┤
│             │                                    │
│  Navigation │         Content Area               │
│             │                                    │
│  ● Home     │                                    │
│  ○ Spider   │     [Current View Content]         │
│  ○ Parser   │                                    │
│  ○ MR Update│                                    │
│  ○ DB Browser│                                   │
│  ○ Settings │                                    │
│             │                                    │
├─────────────┴───────────────────────────────────┤
│ Status: Ready | User: john.doe | Env: Production │
└─────────────────────────────────────────────────┘
```

### Navigation
- Click on menu items to switch between modules
- Use keyboard shortcuts (Ctrl+1 through Ctrl+6)
- Current module highlighted in blue

### Status Bar
- **Left**: Current operation status
- **Center**: Logged-in user
- **Right**: Environment and connection status

## Spider Module

The Spider module automates data collection from financial websites and APIs.

### Daily Update Process

1. **Click "Run Daily Update" button**
   - Automatically fetches from all configured sources
   - Shows progress bar during operation
   - Displays results in activity log

2. **Monitor Progress**
   ```
   [09:30:15] Starting daily update...
   [09:30:20] Fetching ASX announcements...
   [09:30:45] Fetched 125 ASX announcements
   [09:31:00] Fetching Vanguard data...
   [09:31:15] Fetched 50 Vanguard records
   [09:31:30] Daily update complete: 175 records
   ```

### Manual Data Collection

#### Fetch by Date
1. Select target website (ASX/Vanguard/BetaShares)
2. Choose date using calendar widget
3. Click "Fetch" button
4. View results in activity log

#### Fetch by Ticker (ASX only)
1. Enter ticker code (e.g., "FLO")
2. Click "Fetch" button
3. System retrieves last 12 months of announcements

### Data Source Cards

Each data source shows:
- **Last Update Time**: When data was last fetched
- **Quick Actions**: Date and ticker-based fetching
- **Status Indicator**: Green (success), Yellow (warning), Red (error)

### Database Information Panel

Displays:
- Database location
- Table statistics
- Connection status
- Last backup time

## Parser Module

The Parser module extracts structured data from PDF and Excel files.

### Drag-and-Drop Parsing

1. **Drag file into gray drop zone**
   ```
   ┌─────────────────────────────────┐
   │                                 │
   │    Drag PDF or Excel file here  │
   │         or click to browse      │
   │                                 │
   └─────────────────────────────────┘
   ```

2. **Select Template** (or use auto-detect)
   - ASX NZ Distribution
   - Vanguard Distribution
   - BetaShares Distribution
   - Generic (fallback)

3. **Review Extracted Data**
   ```
   Field         | Pattern           | Value      | Comment
   -------------|-------------------|------------|----------
   ex_date      | Ex Date.*(\d+/..) | 2025-01-15 | ✓
   income_rate  | Income.*(\d+\.\d+)| 0.045      | ✓
   tax_rate     | [Default]         | 0.30       | Client default
   ```

4. **Edit Values** (if needed)
   - Click on value field to edit
   - Red highlight indicates validation errors
   - Green checkmark shows valid data

5. **Submit to MR Update**
   - Click "Submit to MR Update" button
   - Data transfers to MR Update module
   - Confirmation message appears

### Batch Processing

1. **Enter folder path** in text field
2. **Select file pattern** (e.g., "*.pdf")
3. **Choose template** or use auto-detect
4. **Click "Process Folder"**
5. **Review results** in summary table

### Template Information

View available fields for each template:
- Required fields marked with asterisk (*)
- Optional fields with default values shown
- Business rules displayed in tooltip

## MR Update Module

The MR Update module submits processed data to the DMH system.

### Task Table

```
Client | Group  | Fund | Asset_ID  | Ex_Date    | Pay_Date   | MR_Income | Type  | Status
-------|--------|------|-----------|------------|------------|-----------|-------|--------
AURR   | LUSC   | REUC | 902XGW000 | 2025-07-31 | 2025-08-06 | 0.89      | Other | Pending
MBFF   |        | MAR1 | 952LEII3  | 2025-07-01 | 2025-10-31 | 0.004461  | Last  | Pending
```

### Adding Tasks

#### Method 1: From Parser
- Tasks automatically appear after parsing
- Pre-filled with extracted data
- Validation already performed

#### Method 2: Manual Entry
1. Click "Add Row" button
2. Fill in required fields:
   - Client ID
   - Asset ID
   - Ex Date
   - MR Income
3. Optional fields auto-populate with defaults
4. Click "Validate" to check data

#### Method 3: Paste from Excel
1. Copy data from Excel
2. Click in table
3. Press Ctrl+V to paste
4. System auto-maps columns

### Submitting to DMH

1. **Review all tasks** in table
   - Yellow rows have warnings
   - Red rows have errors
   - Green rows ready for submission

2. **Click "Submit to DMH"** button
   - Progress bar shows submission status
   - Each row updates with result:
     - ✓ Success (green)
     - ⚠ Warning (yellow)
     - ✗ Failed (red)

3. **Review submission results**
   ```
   Submission Complete
   Successfully updated: 8/10
   Failed: 2/10
   
   View details in log window below
   ```

4. **Handle failures**
   - Double-click failed row for details
   - Correct issues
   - Retry submission

### Backup Files

Automatically created for successful submissions:
- Location: `//shared/backups/mr_updates/`
- Naming: `{Asset_ID}_{Client_ID}_{ExDate}_{Type}.json`
- Example: `902XGW000_AURR_31Jul2025_ACT.json`

### Business Rules Display

View applied business rules:
1. Click "Show Rules" button
2. Rules panel displays:
   - Tax rate calculations
   - Franking adjustments
   - Component summations
   - Client-specific rules

## Database Browser

Query and explore the database directly.

### Running Queries

1. **Enter SQL query** in query editor
   ```sql
   SELECT * FROM asx_info 
   WHERE asx_code = 'FLO' 
   AND pub_date >= '2025-01-01'
   ORDER BY pub_date DESC;
   ```

2. **Click "Execute"** or press F5

3. **View results** in table below
   - Sort by clicking column headers
   - Filter using search box
   - Export to CSV/Excel

### Common Queries

**Recent Announcements:**
```sql
SELECT asx_code, title, pub_date, downloaded
FROM asx_info
WHERE pub_date >= date('now', '-7 days')
ORDER BY pub_date DESC;
```

**Unprocessed PDFs:**
```sql
SELECT * FROM asx_info
WHERE downloaded = 0
AND asx_code IN (SELECT DISTINCT asx_code FROM dmh_exceptions);
```

**Today's Activity:**
```sql
SELECT action, user_id, update_timestamp, success
FROM sys_log
WHERE date(update_timestamp) = date('now')
ORDER BY update_timestamp DESC;
```

### Export Options

1. **Select data** in results table
2. **Right-click** for context menu
3. **Choose export format:**
   - CSV (comma-separated)
   - Excel (.xlsx)
   - JSON
   - Clipboard

### Safety Features

- Read-only mode for non-developers
- Confirmation required for UPDATE/DELETE
- Automatic query timeout (30 seconds)
- Transaction rollback on errors

## Settings

Configure application behavior and preferences.

### File Paths

```
Download Path:    [//shared/downloads/        ] [Browse]
Backup Path:      [//shared/backups/          ] [Browse]
Log Path:         [//shared/logs/             ] [Browse]
Temp Path:        [C:\Users\john\AppData\Temp ] [Browse]
```

### Scraper Settings

```
□ Enable automatic daily updates
  Run at: [09:00] AM

□ Download PDFs automatically
  Max concurrent: [3 ▼]

□ Retry failed operations
  Max retries: [3 ▼]
  
Rate limiting (seconds): [1.0 ▼]
```

### Display Preferences

```
Theme:           [● Dark] [○ Light]
Font Size:       [12 ▼] pt
Date Format:     [DD/MM/YYYY ▼]
Number Format:   [#,##0.00 ▼]

□ Show tooltips
□ Confirm before exit
□ Auto-save work
```

### Log Viewer

Real-time application logs:
```
2025-01-15 09:30:15 [INFO] Application started
2025-01-15 09:30:20 [INFO] Database connected
2025-01-15 09:30:25 [INFO] Spider module loaded
```

Controls:
- **Filter Level**: All, Info, Warning, Error
- **Search**: Find specific messages
- **Export**: Save logs to file
- **Clear**: Clear current view

## Common Workflows

### Daily Morning Process

1. **Launch DMH MR Tool**
2. **Navigate to Spider module** (Ctrl+2)
3. **Click "Run Daily Update"**
4. **Wait for completion** (~5 minutes)
5. **Navigate to Parser module** (Ctrl+3)
6. **Process downloaded PDFs**
7. **Navigate to MR Update** (Ctrl+4)
8. **Review and submit data**
9. **Verify in DMH system**

### Processing Exception Items

1. **Receive exception list from DMH**
2. **Spider module**: Fetch by ticker for each exception
3. **Parser module**: Process downloaded PDFs
4. **MR Update**: Submit with "Template - PIII" type
5. **Document exceptions handled**

### Month-End Processing

1. **Database Browser**: Run month-end report query
2. **Export results to Excel**
3. **Spider module**: Fetch all month-end distributions
4. **Parser module**: Batch process folder
5. **MR Update**: Bulk submit all items
6. **Settings**: Create manual backup

## Troubleshooting

### Common Issues and Solutions

#### Issue: "Cannot connect to database"
**Solution:**
1. Check network connection
2. Verify VPN is connected
3. Check database path in Settings
4. Contact IT if issue persists

#### Issue: "Spider fetch failed"
**Solution:**
1. Check internet connectivity
2. Verify website is accessible
3. Check Settings > Scraper Settings
4. Try manual fetch with specific date
5. Check activity log for details

#### Issue: "PDF parsing returns no data"
**Solution:**
1. Verify PDF is not corrupted
2. Try different template
3. Check if PDF is text-based (not scanned)
4. Use generic template as fallback
5. Manual data entry if needed

#### Issue: "DMH submission failed"
**Solution:**
1. Check DMH system status
2. Verify data validation passed
3. Check user permissions
4. Review error message details
5. Retry after correcting issues

#### Issue: "Application won't start"
**Solution:**
1. Restart Automation Launcher
2. Check for updates in GMAS portal
3. Clear temp files
4. Reinstall if necessary
5. Contact support with error logs

### Error Messages

| Error Message | Meaning | Action |
|--------------|---------|--------|
| "Network timeout" | Connection took too long | Check network/VPN |
| "Invalid template" | PDF doesn't match template | Try different template |
| "Validation failed" | Data doesn't meet rules | Review and correct data |
| "Permission denied" | Insufficient access rights | Contact administrator |
| "Rate limit exceeded" | Too many requests | Wait and retry |

## Keyboard Shortcuts

### Global Shortcuts
- **Ctrl+1**: Home
- **Ctrl+2**: Spider
- **Ctrl+3**: Parser
- **Ctrl+4**: MR Update
- **Ctrl+5**: Database Browser
- **Ctrl+6**: Settings
- **F5**: Refresh current view
- **Ctrl+S**: Save current work
- **Ctrl+Q**: Quit application

### Module-Specific Shortcuts
- **Spider Module**:
  - **Ctrl+U**: Run daily update
  - **Ctrl+D**: Focus date picker
  
- **Parser Module**:
  - **Ctrl+O**: Open file dialog
  - **Ctrl+Enter**: Submit to MR Update
  
- **MR Update Module**:
  - **Ctrl+N**: Add new row
  - **Delete**: Remove selected row
  - **Ctrl+Enter**: Submit to DMH
  
- **Database Browser**:
  - **F5**: Execute query
  - **Ctrl+E**: Export results

## Best Practices

### Data Quality

1. **Always verify parsed data** before submission
2. **Use appropriate templates** for each document type
3. **Check for duplicates** before processing
4. **Review warnings** even if validation passes
5. **Document any manual corrections**

### Performance Optimization

1. **Run daily updates early** (before 9 AM)
2. **Process PDFs in batches** when possible
3. **Use date ranges** to limit data fetching
4. **Clear old data regularly** (Database Browser)
5. **Close unused modules** to free memory

### Security

1. **Never share your login** credentials
2. **Lock your workstation** when away
3. **Report suspicious data** immediately
4. **Use read-only queries** when browsing
5. **Follow data retention policies**

### Backup and Recovery

1. **Let automatic backups run** (don't interrupt)
2. **Verify backup files** periodically
3. **Export important queries** for reuse
4. **Document custom templates**
5. **Keep local copies** of critical configurations

### Collaboration

1. **Coordinate processing times** with team
2. **Use consistent naming** for templates
3. **Share useful queries** via Database Browser
4. **Report bugs promptly** with details
5. **Suggest improvements** through feedback

## Support

### Getting Help

1. **In-Application Help**: Press F1 in any module
2. **User Documentation**: This guide
3. **IT Help Desk**: ext. 1234
4. **Development Team**: dmh-support@company.com
5. **Emergency Support**: +1-234-567-8900

### Reporting Issues

When reporting issues, provide:
1. Screenshot of error
2. Steps to reproduce
3. Time of occurrence
4. Module where error occurred
5. Any error messages
6. Recent actions taken

### Feature Requests

Submit feature requests via:
- Email: dmh-features@company.com
- Include business justification
- Describe expected behavior
- Provide use case examples

## Appendix

### Glossary

| Term | Definition |
|------|------------|
| **ASX** | Australian Securities Exchange |
| **DMH** | Data Management Hub (internal system) |
| **MR** | Master Rate |
| **Spider** | Automated web data collector |
| **Parser** | Document data extractor |
| **Template** | Predefined extraction pattern |
| **GMAS** | Global Management Automation System |

### File Formats Supported

- **PDF**: Distribution announcements, statements
- **Excel**: .xlsx, .xls, .xlsm spreadsheets
- **CSV**: Comma-separated values
- **JSON**: API responses, configuration files

### Regular Expressions Used

Common patterns in templates:
- Date: `\d{1,2}[/-]\d{1,2}[/-]\d{4}`
- Currency: `\$?\d+(?:,\d{3})*(?:\.\d{2})?`
- Percentage: `\d+(?:\.\d+)?%?`
- Ticker: `[A-Z]{3,4}`

### Change Log

See `CHANGELOG.md` for version history and updates.