# src/dmh_mr_tool/ui/views/manual_view.py
"""Manual Interface for displaying user guide and business rules"""

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QSplitter
from qfluentwidgets import (
    ScrollArea, PrimaryPushButton, PushButton, StrongBodyLabel,
    FluentIcon as FIF, CardWidget, InfoBar, InfoBarPosition
)

from ui.views.base_view import BaseInterface
from ui.utils.signal_bus import signalBus
from ui.utils.infobar import createSuccessInfoBar, createErrorInfoBar, createWarningInfoBar
from config.settings import CONFIG

import structlog

logger = structlog.get_logger()


class MarkdownViewer(QTextEdit):
    """Custom text edit widget for displaying markdown content"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                border: 1px solid #e1e1e1;
                border-radius: 6px;
                padding: 16px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.6;
            }
            QTextEdit[darkMode="true"] {
                background-color: #1e1e1e;
                border: 1px solid #3c3c3c;
                color: #d4d4d4;
            }
        """)


class ManualInterface(BaseInterface):
    """Manual Interface for displaying user guide and business rules"""

    def __init__(self, parent=None):
        super().__init__(
            title="Manual",
            subtitle="User guide and business rules for DMH MR Tool",
            parent=parent
        )
        self.setObjectName('manualInterface')
        self.manual_file_path = self.getManualFilePath()
        self.initUI()
        self.loadManualContent()

    def getManualFilePath(self) -> Path:
        """Get the path to the manual markdown file"""
        # Try to find manual file in different locations
        possible_paths = [
            Path(__file__).parent.parent.parent / "docs" / "manual_content.md",
            Path(__file__).parent.parent.parent / "manual_content.md",
            Path.cwd() / "docs" / "manual_content.md",
            Path.cwd() / "manual_content.md",
        ]

        for path in possible_paths:
            if path.exists():
                return path

        # If not found, use the first path as default location
        return possible_paths[0]

    def initUI(self):
        """Initialize the user interface"""
        # Main content area
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(16)

        # Control buttons
        self.addControlButtons(main_layout)

        # Content viewer
        self.addContentViewer(main_layout)

        # File info
        self.addFileInfo(main_layout)

        self.addPageBody("", main_widget, stretch=1)

    def addControlButtons(self, layout):
        """Add control buttons section"""
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setSpacing(12)

        # Reload button
        self.reloadBtn = PrimaryPushButton("Reload Manual", controls_widget)
        self.reloadBtn.setIcon(FIF.SYNC)
        self.reloadBtn.clicked.connect(self.loadManualContent)

        # Open file button
        self.openFileBtn = PushButton("Open File Location", controls_widget)
        self.openFileBtn.setIcon(FIF.FOLDER)
        self.openFileBtn.clicked.connect(self.openFileLocation)

        # Edit button
        self.editBtn = PushButton("Edit Manual", controls_widget)
        self.editBtn.setIcon(FIF.EDIT)
        self.editBtn.clicked.connect(self.editManual)

        controls_layout.addWidget(self.reloadBtn)
        controls_layout.addWidget(self.openFileBtn)
        controls_layout.addWidget(self.editBtn)
        controls_layout.addStretch()

        # Wrap in card
        controls_card = CardWidget()
        controls_card.setLayout(QVBoxLayout())
        controls_card.layout().addWidget(StrongBodyLabel("Manual Controls"))
        controls_card.layout().addWidget(controls_widget)
        controls_card.setFixedHeight(80)

        layout.addWidget(controls_card)

    def addContentViewer(self, layout):
        """Add markdown content viewer"""
        # Content viewer
        self.contentViewer = MarkdownViewer()
        self.contentViewer.setMinimumHeight(500)

        # Wrap in card
        content_card = CardWidget()
        content_card.setLayout(QVBoxLayout())
        content_card.layout().addWidget(StrongBodyLabel("User Manual"))
        content_card.layout().addWidget(self.contentViewer)

        layout.addWidget(content_card)

    def addFileInfo(self, layout):
        """Add file information section"""
        self.fileInfoLabel = StrongBodyLabel("", self)
        self.fileInfoLabel.setStyleSheet("QLabel { color: #666; font-size: 12px; }")

        info_card = CardWidget()
        info_card.setLayout(QVBoxLayout())
        info_card.layout().addWidget(self.fileInfoLabel)
        info_card.setFixedHeight(50)

        layout.addWidget(info_card)

    def loadManualContent(self):
        """Load manual content from markdown file"""
        try:
            if self.manual_file_path.exists():
                # Read markdown file
                with open(self.manual_file_path, 'r', encoding='utf-8') as file:
                    markdown_content = file.read()

                # Convert markdown to HTML (basic conversion)
                html_content = self.markdownToHtml(markdown_content)

                # Set content
                self.contentViewer.setHtml(html_content)

                # Update file info
                file_size = self.manual_file_path.stat().st_size
                modified_time = self.manual_file_path.stat().st_mtime
                import datetime
                modified_str = datetime.datetime.fromtimestamp(modified_time).strftime("%Y-%m-%d %H:%M:%S")

                self.fileInfoLabel.setText(
                    f"File: {self.manual_file_path.name} | "
                    f"Size: {file_size:,} bytes | "
                    f"Modified: {modified_str}"
                )

                createSuccessInfoBar(self, "Manual Loaded", "Manual content loaded successfully")
                logger.info(f"Manual content loaded from {self.manual_file_path}")

            else:
                # Create default content if file doesn't exist
                self.createDefaultManual()
                createWarningInfoBar(
                    self,
                    "Manual Not Found",
                    f"Manual file not found. Created default at {self.manual_file_path}"
                )

        except Exception as e:
            error_msg = f"Failed to load manual: {str(e)}"
            createErrorInfoBar(self, "Load Error", error_msg)
            logger.error(f"Manual load error: {e}")

            # Show error in viewer
            self.contentViewer.setPlainText(f"Error loading manual content:\n\n{error_msg}")
            self.fileInfoLabel.setText("Error loading file")

    def markdownToHtml(self, markdown_text: str) -> str:
        """Convert markdown to HTML (basic implementation)"""
        lines = markdown_text.split('\n')
        html_lines = []
        in_code_block = False

        # Basic HTML structure
        html_lines.append("""
        <html>
        <head>
            <style>
                body { 
                    font-family: 'Segoe UI', Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #333;
                    max-width: 100%;
                    margin: 0;
                    padding: 20px;
                }
                h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
                h2 { color: #34495e; margin-top: 30px; }
                h3 { color: #7f8c8d; margin-top: 25px; }
                h4 { color: #95a5a6; margin-top: 20px; }
                code { 
                    background-color: #f8f9fa; 
                    padding: 2px 6px; 
                    border-radius: 3px; 
                    font-family: 'Consolas', monospace;
                    font-size: 90%;
                }
                pre { 
                    background-color: #f8f9fa; 
                    padding: 15px; 
                    border-radius: 5px; 
                    border-left: 4px solid #3498db;
                    overflow-x: auto;
                }
                blockquote { 
                    border-left: 4px solid #bdc3c7; 
                    padding-left: 20px; 
                    margin-left: 0; 
                    font-style: italic;
                    color: #7f8c8d;
                }
                ul, ol { margin: 10px 0; padding-left: 30px; }
                li { margin: 5px 0; }
                strong { color: #2c3e50; }
                em { color: #e67e22; }
                hr { border: none; height: 1px; background-color: #bdc3c7; margin: 30px 0; }
                .workflow { background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 10px 0; }
            </style>
        </head>
        <body>
        """)

        for line in lines:
            line = line.rstrip()

            # Code blocks
            if line.startswith('```'):
                if in_code_block:
                    html_lines.append('</pre>')
                    in_code_block = False
                else:
                    html_lines.append('<pre><code>')
                    in_code_block = True
                continue

            if in_code_block:
                html_lines.append(line)
                continue

            # Headers
            if line.startswith('# '):
                html_lines.append(f'<h1>{line[2:]}</h1>')
            elif line.startswith('## '):
                html_lines.append(f'<h2>{line[3:]}</h2>')
            elif line.startswith('### '):
                html_lines.append(f'<h3>{line[4:]}</h3>')
            elif line.startswith('#### '):
                html_lines.append(f'<h4>{line[5:]}</h4>')

            # Horizontal rule
            elif line.strip() == '---':
                html_lines.append('<hr>')

            # Lists
            elif line.startswith('- ') or line.startswith('* '):
                html_lines.append(f'<ul><li>{line[2:]}</li></ul>')
            elif line.strip() and line[0].isdigit() and '. ' in line:
                content = line.split('. ', 1)[1]
                html_lines.append(f'<ol><li>{content}</li></ol>')

            # Blockquotes
            elif line.startswith('> '):
                html_lines.append(f'<blockquote>{line[2:]}</blockquote>')

            # Empty lines
            elif line.strip() == '':
                html_lines.append('<br>')

            # Regular paragraphs
            else:
                # Process inline formatting
                processed_line = line
                # Bold
                processed_line = processed_line.replace('**', '<strong>').replace('**', '</strong>')
                # Italic
                processed_line = processed_line.replace('*', '<em>').replace('*', '</em>')
                # Inline code
                import re
                processed_line = re.sub(r'`([^`]+)`', r'<code>\1</code>', processed_line)

                html_lines.append(f'<p>{processed_line}</p>')

        html_lines.append('</body></html>')

        return '\n'.join(html_lines)

    def createDefaultManual(self):
        """Create default manual content if file doesn't exist"""
        default_content = """# DMH MR Tool User Manual

## Overview
Welcome to the DMH MR Tool - your automated solution for financial data processing.

## Quick Start Guide
1. **Spider Interface**: Fetch data from external sources
2. **Parser Interface**: Extract data from documents
3. **MR Update Interface**: Submit data to DMH system
4. **DB Browser**: Query and examine database
5. **Settings**: Configure application preferences

## Need Help?
- Contact your system administrator
- Check the application logs in Settings
- Review error messages for specific guidance

---
*This is a default manual. Please edit the manual_content.md file to customize this content.*
"""

        try:
            # Ensure directory exists
            self.manual_file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write default content
            with open(self.manual_file_path, 'w', encoding='utf-8') as file:
                file.write(default_content)

            logger.info(f"Default manual created at {self.manual_file_path}")

        except Exception as e:
            logger.error(f"Failed to create default manual: {e}")

    def openFileLocation(self):
        """Open the file location in system explorer"""
        try:
            import subprocess
            import platform

            file_path = str(self.manual_file_path.parent)

            if platform.system() == "Windows":
                subprocess.run(['explorer', file_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(['open', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])

            createSuccessInfoBar(self, "Folder Opened", "Manual folder opened in file explorer")

        except Exception as e:
            createErrorInfoBar(self, "Open Error", f"Failed to open folder: {str(e)}")
            logger.error(f"Failed to open file location: {e}")

    def editManual(self):
        """Open manual file in default text editor"""
        try:
            import subprocess
            import platform

            file_path = str(self.manual_file_path)

            if platform.system() == "Windows":
                subprocess.run(['notepad.exe', file_path])
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(['open', '-t', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])

            createSuccessInfoBar(self, "Editor Opened", "Manual file opened for editing")

        except Exception as e:
            createErrorInfoBar(self, "Edit Error", f"Failed to open editor: {str(e)}")
            logger.error(f"Failed to open manual for editing: {e}")