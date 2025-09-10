# DMH MR Tool User Manual

## Overview

The DMH MR Tool is a lightweight internal automation utility designed to streamline the manual process of collecting, extracting, and processing Australian financial market data. It helps reduce daily processing time from 2-3 hours to under 30 minutes while minimizing human error.

## Getting Started

### 1. Home Interface
- **Purpose**: Software usage dashboard and overview
- **Features**: Quick status overview of all components

### 2. Spider Interface
- **Purpose**: Fetch announcement data from external sources
- **Key Functions**:
  - Download today's or previous business day's ASX announcements
  - Fetch specific company announcements by ASX code and year
  - Run daily spider process for all data sources
  - Sync PDF URLs for downloaded announcements

### 3. Parser Interface
- **Purpose**: Extract data from PDF and Excel documents
- **Workflow**:
  1. **Upload Document**: Drag and drop or browse for files (PDF/Excel)
  2. **Select Template**: Choose appropriate parsing template
  3. **Parse**: Extract data using regex patterns
  4. **Review**: Check and edit extracted values
  5. **Submit**: Send to MR Update Interface

### 4. MR Update Interface
- **Purpose**: Manage and submit business records to DMH system
- **Features**:
  - View parsed business records in table format
  - Fetch PDFs automatically using ASX code and dates
  - Submit selected records to DMH system
  - Track submission status in real-time
  - Backup successful submissions automatically

### 5. DB Browser Interface
- **Purpose**: Query and browse database content
- **Access Control**: Only developers can execute write operations
- **Features**:
  - Run SQL queries with predefined templates
  - Export results to CSV
  - Copy data to clipboard

### 6. Settings Interface
- **Purpose**: Configure application settings and view logs
- **Features**:
  - Modify file paths (download, backup, logs)
  - View real-time log files
  - Configure system preferences

## Business Rules

### Data Processing Rules

#### ASX Announcements
- **Daily Fetch**: Automatically fetches previous business day announcements
- **Duplicate Prevention**: System checks for existing announcements before saving
- **URL Sync**: PDF mask URLs are converted to actual PDF URLs when needed
- **Download Strategy**: PDFs are only downloaded when specifically needed (via Fetch button)

#### Parsing Templates
- **Template Types**:
  - **MR Templates**: For general dividend/distribution data
  - **NZ Templates**: For New Zealand specific data
  - **Hi-Trust UR**: For batch processing actual values (ACT type)
  - **Others**: EST type for estimates

#### Validation Rules
- **Required Fields**: ex_date, pay_date, asset_id must be present
- **Data Types**: Numeric fields validated for proper format
- **Date Formats**: Multiple date formats supported (DD/MM/YYYY, YYYY-MM-DD, etc.)

#### Business Logic
- **Tax Rate Default**: 0.3 (30%) for ASX MIT Notice template
- **Total Calculation**: Sum of DOM_INC + FOR_INC + DOM_DID for Vanguard template
- **Currency Handling**: AUD/NZD exchange rates applied where applicable

### File Management

#### Backup Policy
- **Trigger**: Successful DMH submission
- **Naming Convention**: `{Asset_ID}_{Client_ID}_{Ex_Date_ddMMMyyy}_{ACT|EST}`
- **Location**: Configured backup path in settings
- **Retention**: Manual cleanup by developers annually

#### Download Management
- **PDF Storage**: Shared network drive location
- **Status Tracking**: Downloaded/Failed status in database
- **Cleanup**: PDFs can be manually removed as needed

### Access Control

#### User Permissions
- **All Users**: Can access all interfaces and run SELECT queries
- **Developers Only**: Can execute INSERT/UPDATE/DELETE SQL operations
- **Write Operations**: Require confirmation dialog

#### Security
- **Database**: SQLite with Write-Ahead Logging
- **Network**: Shared drive access required
- **Authentication**: Windows authentication used

## Workflow Examples

### Daily Processing Workflow
1. **Morning Setup**:
   - Open DMH MR Tool
   - Check Spider interface for data source status
   - Run daily spider to fetch latest announcements

2. **Exception Processing**:
   - Review MR Update interface for pending items
   - Use Fetch button for missing PDFs
   - Parse documents using appropriate templates
   - Submit validated records to DMH

3. **Validation**:
   - Check submission status
   - Verify backup files created
   - Review any failed submissions

### Manual Document Processing
1. **Document Receipt**:
   - Save document to processing folder or drag-drop to Parser
   - Select appropriate template based on source/type

2. **Data Extraction**:
   - Review parsed values for accuracy
   - Edit any incorrect extractions
   - Add missing fields manually

3. **Submission**:
   - Enter header information (Client_ID, Asset_ID, dates)
   - Submit to MR Update interface
   - Monitor submission progress

### Batch Processing (Hi-Trust UR)
1. **Folder Setup**:
   - Place all files in designated folder
   - Ensure files follow naming conventions

2. **Batch Process**:
   - Enter folder path in Parser interface
   - Click "Batch Process" with Hi-Trust UR template
   - Monitor progress and results

3. **Review**:
   - Check MR Update interface for all processed items
   - Submit batch to DMH system

## Troubleshooting

### Common Issues

#### Spider Issues
- **No Data**: Check internet connection and website availability
- **Failed Downloads**: Verify proxy settings and file permissions
- **Duplicate Warnings**: Normal behavior, indicates data already exists

#### Parser Issues
- **No Values Extracted**: Check template patterns and document format
- **Incorrect Dates**: Verify date format in source document
- **Missing Fields**: Use manual entry for non-standard documents

#### Submission Issues
- **DMH Login Failed**: Check credentials and network connectivity
- **Validation Errors**: Review required fields and data formats
- **Partial Success**: Successfully submitted items are marked and locked

### Error Recovery
- **Failed Submissions**: Items remain editable for retry
- **Database Errors**: Check file permissions and disk space
- **Network Issues**: Retry after connectivity restored

## Configuration

### File Paths
- **Download Path**: Where PDFs are saved
- **Backup Path**: Where successful submissions are backed up
- **Log Path**: Where application logs are stored
- **Temp Path**: Temporary file processing location

### Database
- **Main Database**: SQLite file on shared drive
- **Backup Database**: Automatic backups with timestamps
- **Connection**: Managed automatically by application

### Templates
- **Location**: Stored in database for easy modification
- **Types**: MR and NZ templates available
- **Patterns**: Regular expressions for data extraction

## Support

### For Users
- Check this manual for common procedures
- Review error messages in info bars
- Check system logs for detailed error information

### For Developers
- Access Settings interface for log files
- Use DB Browser for database inspection
- Modify templates and business rules as needed
- Update this manual when procedures change

---

*Last Updated: 2025-01-13*
*Version: 1.0*